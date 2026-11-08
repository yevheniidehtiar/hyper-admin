"""User-cache fixture app for E2E testing (st-perf-04).

Started by the ``user_cache_base_url`` fixture in ``tests/e2e/test_user_cache_journeys.py``.
The cache TTL comes from ``E2E_USER_CACHE_TTL`` (default ``5``; ``0`` = off), so one journey
can run with and without the cache. The cache clock is a fake the tests advance with
``POST /_test/advance``, so "the TTL has passed" needs no sleeping.

Registers ``Ticket`` (45 rows, so the list has several pages) with search, a category filter
(15 rows per category; the date range makes the sidebar render), sorting and an editable status
column.

Users (password ``secret123``):

* ``alice``, ``boss`` - superusers.
* ``staff``, ``temp``, ``pwuser`` - view, add, change and delete ticket (direct grants).
* ``viewer`` - ``view_ticket`` only.
* ``grouped`` - view and change ticket through the ``Support`` group only.

Host routes outside the admin (no auth), to act as "someone else" or "another worker":

* ``POST /_test/set?user=&field=&value=&via=`` - set ``is_active`` / ``is_superuser`` through
  the ORM (``orm``), a bulk Core UPDATE in a session (``bulk``), or a bare connection that no
  session listener sees (``raw``, i.e. another worker or a CLI).
* ``POST /_test/revoke?user=&codename=&via=`` - remove a direct permission the same ways.
* ``POST /_test/leave_group?user=`` - remove the user from every group.
* ``POST /_test/password?user=&password=`` - change a password through the ORM.
* ``POST /_test/advance?seconds=`` - move the cache clock forward.
* ``GET /_test/queries`` / ``POST /_test/reset`` - SQL statements run since the last reset.
"""

from __future__ import annotations

import enum
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from sqlalchemy import delete, event, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth import user_cache
from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.filters import DateRangeFilter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_usercache_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)

TTL = int(os.environ.get("E2E_USER_CACHE_TTL", "5"))
FULL = ("view_ticket", "add_ticket", "change_ticket", "delete_ticket")
STATEMENTS: list[str] = []


class _Clock:
    now = 1000.0


_original_init = user_cache.UserCache.__init__


def _init_with_fake_clock(self: user_cache.UserCache, ttl: float, **kwargs: Any) -> None:
    kwargs["clock"] = lambda: _Clock.now
    _original_init(self, ttl, **kwargs)


user_cache.UserCache.__init__ = _init_with_fake_clock  # type: ignore[method-assign]


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _record(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
    STATEMENTS.append(statement)


class Category(enum.Enum):
    BUG = "bug"
    FEATURE = "feature"
    QUESTION = "question"


class Ticket(SQLModel, table=True):
    __tablename__ = "e2e_uc_ticket"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=80)
    status: str = Field(default="open", max_length=20)
    category: Category = Field(default=Category.BUG)
    created_on: date = Field(default=date(2024, 1, 1))

    def __str__(self) -> str:
        return self.title


class TicketAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(
        list_display=["title", "status"],
        search_fields=["title"],
        list_filter=["category", DateRangeFilter(field="created_on")],
        list_editable=["status"],
    )


async def _seed() -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if (await session.execute(select(User).where(User.username == "alice"))).first():
            return
        names = ("alice", "boss", "staff", "temp", "pwuser", "viewer", "grouped")
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password_hash=hash_password("secret123"),
                is_superuser=name in ("alice", "boss"),
            )
            for name in names
        }
        support = Group(name="Support")
        session.add_all([*users.values(), support])
        session.add_all(
            Ticket(title=f"Ticket {i:02d}", category=list(Category)[i % 3]) for i in range(1, 46)
        )
        await session.commit()
        ids = dict((await session.execute(select(Permission.codename, Permission.id))).all())
        grants = {
            **dict.fromkeys(("staff", "temp", "pwuser"), FULL),
            "viewer": ("view_ticket",),
        }
        session.add_all(
            UserPermission(user_id=users[name].id, permission_id=ids[codename])
            for name, codenames in grants.items()
            for codename in codenames
        )
        session.add_all(
            GroupPermission(group_id=support.id, permission_id=ids[codename])
            for codename in ("view_ticket", "change_ticket")
        )
        session.add(UserGroup(user_id=users["grouped"].id, group_id=support.id))
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await admin._sync_permissions()
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)


async def _user_id(session: AsyncSession, username: str) -> int:
    row = (await session.execute(select(User.id).where(User.username == username))).scalar_one()
    return int(row)


@app.post("/_test/set")
async def set_flag(user: str, field: str, value: int, via: str = "orm") -> dict[str, bool]:
    """Set ``is_active`` or ``is_superuser`` via the ORM, a session bulk UPDATE or a bare connection."""
    assert field in ("is_active", "is_superuser")
    if via == "raw":
        table = User.__table__  # type: ignore[attr-defined]
        async with engine.begin() as conn:
            await conn.execute(
                update(table).where(table.c.username == user).values({field: bool(value)})
            )
        return {"ok": True}
    async with AsyncSession(engine) as session:
        if via == "bulk":
            await session.execute(
                update(User).where(User.username == user).values({field: bool(value)})  # type: ignore[arg-type]
            )
        else:
            row = (await session.execute(select(User).where(User.username == user))).scalar_one()
            setattr(row, field, bool(value))
            session.add(row)
        await session.commit()
    return {"ok": True}


@app.post("/_test/revoke")
async def revoke(user: str, codename: str, via: str = "orm") -> dict[str, bool]:
    """Remove one direct permission."""
    async with AsyncSession(engine) as session:
        uid = await _user_id(session, user)
        pid = (
            await session.execute(select(Permission.id).where(Permission.codename == codename))
        ).scalar_one()
        if via == "raw":
            table = UserPermission.__table__  # type: ignore[attr-defined]
            async with engine.begin() as conn:
                await conn.execute(
                    delete(table).where(table.c.user_id == uid, table.c.permission_id == pid)
                )
            return {"ok": True}
        if via == "bulk":
            await session.execute(
                delete(UserPermission).where(
                    UserPermission.user_id == uid,  # type: ignore[arg-type]
                    UserPermission.permission_id == pid,  # type: ignore[arg-type]
                )
            )
        else:
            row = (
                await session.execute(
                    select(UserPermission).where(
                        UserPermission.user_id == uid,  # type: ignore[arg-type]
                        UserPermission.permission_id == pid,  # type: ignore[arg-type]
                    )
                )
            ).scalar_one()
            await session.delete(row)
        await session.commit()
    return {"ok": True}


@app.post("/_test/leave_group")
async def leave_group(user: str) -> dict[str, bool]:
    """Remove the user from every group through the ORM."""
    async with AsyncSession(engine) as session:
        uid = await _user_id(session, user)
        rows = (
            (await session.execute(select(UserGroup).where(UserGroup.user_id == uid)))  # type: ignore[arg-type]
            .scalars()
            .all()
        )
        for row in rows:
            await session.delete(row)
        await session.commit()
    return {"ok": True}


@app.post("/_test/password")
async def change_password(user: str, password: str) -> dict[str, bool]:
    """Change a user's password through the ORM."""
    async with AsyncSession(engine) as session:
        row = (await session.execute(select(User).where(User.username == user))).scalar_one()
        row.password_hash = hash_password(password)
        session.add(row)
        await session.commit()
    return {"ok": True}


@app.post("/_test/advance")
async def advance(seconds: float) -> dict[str, float]:
    """Move the cache clock forward."""
    _Clock.now += seconds
    return {"now": _Clock.now}


@app.post("/_test/reset")
async def reset() -> dict[str, bool]:
    """Forget the recorded SQL statements."""
    STATEMENTS.clear()
    return {"ok": True}


@app.get("/_test/queries")
async def queries() -> dict[str, int]:
    """Count recorded SELECTs on the user table and on the permission tables."""
    selects = [s for s in STATEMENTS if s.lstrip().upper().startswith("SELECT")]
    return {
        "user": sum("FROM hyperadmin_users" in s for s in selects),
        "permissions": sum("hyperadmin_permissions" in s for s in selects),
    }


site._registry = {}
site.register(Ticket, TicketAdmin)

admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(
        create_tables=False,
        secret_key="e2e-user-cache-secret",
        auto_discover=False,
        user_cache_ttl=TTL,
    ),
    auth_backend=SessionAuthBackend(engine=engine),
    permission_checker=ModelPermissionChecker(engine=engine),
    permission_registry=PermissionSyncService(engine=engine),
)
admin.mount(path="/admin")
