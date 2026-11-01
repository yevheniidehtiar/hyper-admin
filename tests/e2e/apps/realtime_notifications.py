"""Auth + realtime HyperAdmin app for the live CRUD notification E2E tests (#313).

Spec: ``docs/specs/realtime-crud-notifications.md``. Started by the fixtures in
``test_realtime_notifications.py`` via a uvicorn subprocess. ``RT_MODE`` picks the variant:

* ``default`` (unset) -- ``RealtimeSettings()``: notifications on for every model.
* ``optin`` -- ``RealtimeSettings(notifications=False)`` and only ``ArticleAdmin`` sets
  ``realtime_notifications=True``.
* ``off`` -- ``Admin(realtime=None)``.

Users (password ``secret123``, no first/last name so toasts show the username):
``alice`` (id 1) and ``bob`` (id 2) are superusers; ``carol`` (id 3) holds no permission.

Models: ``Article`` (42 seeded rows, alternating ``draft``/``published``), ``Comment`` and
``Note``. ``NoteAdmin.get_queryset`` limits every user to the notes whose ``owner`` is their
own user id (3 notes each for alice and bob).
"""

from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin import RealtimeSettings
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import User
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.requests import Request

MODE = os.environ.get("RT_MODE", "default")
ARTICLE_COUNT = 42

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_rtn_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class Article(SQLModel, table=True):
    __tablename__ = "e2e_rtn_article"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(min_length=1)
    status: str = "draft"
    owner: str = ""


class Comment(SQLModel, table=True):
    __tablename__ = "e2e_rtn_comment"

    id: int | None = Field(default=None, primary_key=True)
    body: str = Field(min_length=1)


class Note(SQLModel, table=True):
    __tablename__ = "e2e_rtn_note"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(min_length=1)
    owner: int = 0


class ArticleAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(
        list_filter=["status"],
        realtime_notifications=True if MODE == "optin" else None,
    )


class CommentAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class NoteAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        user = getattr(getattr(request, "state", None), "user", None)
        return {"owner": user.id if user is not None else -1}


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        if (await session.execute(select(User))).first() is None:
            for uid, name, superuser in ((1, "alice", True), (2, "bob", True), (3, "carol", False)):
                session.add(
                    User(
                        id=uid,
                        username=name,
                        email=f"{name}@example.com",
                        password_hash=hash_password("secret123"),
                        is_superuser=superuser,
                    )
                )
            session.add_all(
                Article(
                    title=f"Article {i:02d}",
                    status="draft" if i % 2 == 0 else "published",
                    owner="seed",
                )
                for i in range(1, ARTICLE_COUNT + 1)
            )
            session.add_all(Comment(body=f"Comment {i}") for i in range(1, 4))
            session.add_all(
                Note(title=f"{name} note {i}", owner=uid)
                for uid, name in ((1, "alice"), (2, "bob"))
                for i in range(1, 4)
            )
            await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-realtime-notifications-secret",
    auto_discover=False,
)

site._registry = {}
site.register(Article, ArticleAdmin)
site.register(Comment, CommentAdmin)
site.register(Note, NoteAdmin)

_realtime: RealtimeSettings | None
if MODE == "off":
    _realtime = None
elif MODE == "optin":
    _realtime = RealtimeSettings(heartbeat_interval=1.0, notifications=False)
else:
    _realtime = RealtimeSettings(heartbeat_interval=1.0)

admin = Admin(
    app,
    engine=engine,
    settings=settings,
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
    realtime=_realtime,
)
admin.mount(path="/admin")
