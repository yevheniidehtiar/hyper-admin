"""Bring your own app: HyperAdmin added to an existing FastAPI application.

The host app below already has everything a real app has before an admin
arrives: its own lifespan (it creates its own tables, as Alembic would), its own
``/static`` mount, its own ``session`` cookie, a JWT-protected ``/api`` and a
user model keyed by UUID. Adding the admin takes the block marked
"HyperAdmin" near the end of this file, and changes nothing outside ``/admin``.

Run it::

    HYPERADMIN_DEBUG=true uv run uvicorn examples.byoa.main:app --reload

``HYPERADMIN_DEBUG=true`` lets the admin start with its default secret key for
local development; without it (and without ``HYPERADMIN_SECRET_KEY``) the admin
refuses to start, exactly as it would in your app. The host's own
``BYOA_SESSION_SECRET`` and ``BYOA_JWT_SECRET`` fall back to demo values with a
logged warning (``examples/byoa/config.py``).

Then open http://127.0.0.1:8000/admin/ and sign in as ``ada`` / ``lovelace``
(superuser) or ``grace`` / ``hopper`` (staff, view-only). These seeded accounts,
with their published passwords, are demo data: delete them before any
deployment, and do not point ``BYOA_DATABASE_URL`` at a database you care about.

The database is in memory by default; set ``BYOA_DATABASE_URL`` (for example
``sqlite+aiosqlite:///byoa.db``) to keep data between runs.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, ClassVar

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm  # noqa: TC002 - FastAPI reads it at runtime
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from starlette.middleware.sessions import SessionMiddleware

from examples.byoa.auth import authenticate, get_current_user, hash_password, issue_token
from examples.byoa.config import demo_secret
from examples.byoa.models import HOST_TABLES, Account, Country, Project
from hyperadmin import Admin, HyperAdminSettings
from hyperadmin.auth import ExternalAuth, TokenCookie
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

HERE = Path(__file__).parent
DATABASE_URL = os.environ.get("BYOA_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


async def seed() -> None:
    """Insert the demo rows once.

    Demo data only: the two accounts below have published passwords. A real app
    creates its users through its own sign-up or management command.
    """
    async with sessionmaker() as session:
        if (await session.execute(select(Account))).first() is not None:
            return
        session.add_all(
            [
                Account(
                    username="ada",
                    full_name="Ada Lovelace",
                    password_hash=hash_password("lovelace"),
                    is_superuser=True,
                ),
                Account(
                    username="grace",
                    full_name="Grace Hopper",
                    password_hash=hash_password("hopper"),
                    is_staff=True,
                ),
                Country(code="NL", name="Netherlands"),
                Country(code="FR", name="France"),
            ]
        )
        await session.commit()
        session.add_all(
            [
                Project(name="Analytical Engine", country_code="NL"),
                Project(name="Compiler", country_code="FR"),
            ]
        )
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The host's own lifespan; the admin's lifespan is composed into it."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=HOST_TABLES)
    await seed()
    app.state.sessionmaker = sessionmaker
    # Runs the admin's startup now and drains realtime connections on shutdown.
    async with admin.lifespan():
        yield


app = FastAPI(title="BYOA host", lifespan=lifespan)
# Demo-only fallback, never ship this: a real app reads os.environ["BYOA_SESSION_SECRET"].
app.add_middleware(
    SessionMiddleware, secret_key=demo_secret("BYOA_SESSION_SECRET", "byoa-demo-session")
)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

CurrentUser = Annotated[Account | None, Depends(get_current_user)]


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/")
def home(request: Request) -> dict[str, Any]:
    """Count visits in the host's own ``session`` cookie."""
    request.session["visits"] = int(request.session.get("visits", 0)) + 1
    return {"visits": request.session["visits"], "admin": "/admin/"}


@app.post("/token")
async def token(
    request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> dict[str, str]:
    """The host's OAuth2 password-grant endpoint."""
    account = await authenticate(request, form.username, form.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"access_token": issue_token(account.username), "token_type": "bearer"}


@app.get("/api/me")
def me(user: CurrentUser) -> dict[str, Any]:
    """A JWT-protected API route."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": str(user.id), "username": user.username}


@app.get("/api/projects")
async def projects(user: CurrentUser) -> list[dict[str, Any]]:
    """Another JWT-protected API route."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with sessionmaker() as session:
        rows = (await session.execute(select(Project).order_by(Project.name))).scalars()
        return [{"id": str(p.id), "name": p.name} for p in rows]


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    """The host's login page.

    It gets a token from ``/token``, hands it to the admin with
    ``POST /admin/auth/session`` (the admin stores it in an ``HttpOnly``
    cookie scoped to ``/admin``) and returns to ``next``.
    """
    return (HERE / "login.html").read_text(encoding="utf-8")


# ── HyperAdmin ──────────────────────────────────────────────────────────────


class ProjectAdmin(ModelAdmin):
    list_display: ClassVar[list[str]] = ["name", "country_code"]


site.register(Project, ProjectAdmin)
site.register(Country)
site.register(Account)  # the host user model: superusers edit it, staff only view it

admin = Admin(
    app,
    session_factory=sessionmaker,
    # Reads HYPERADMIN_SECRET_KEY; the default key is refused unless HYPERADMIN_DEBUG=true.
    settings=HyperAdminSettings(),
    auth=ExternalAuth(
        get_user=get_current_user,
        login_url="/login",
        logout_url="/",
        token_cookie=TokenCookie(),
    ),
)
admin.mount("/admin")
