"""Query-count tests for resolving a user's permissions once per request (st-perf-05)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.auth.permissions import (
    ModelPermissionChecker,
    PermissionSyncService,
    forget_user_permissions,
)
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views import permissions_matrix as matrix_views
from tests.conftest import with_csrf

pytestmark = pytest.mark.anyio

SECRET = "test-secret"
PASSWORD = "password123"
MODEL_COUNT = 20
#: The list page of the story's ``GET /admin/invoice/`` (the route has no trailing slash).
LIST_URL = "/admin/invoice"
#: The link tables only the permission step reads.
PERMISSION_TABLES = ("hyperadmin_user_permissions", "hyperadmin_group_permissions")


class Invoice(SQLModel, table=True):
    __tablename__ = "pqc_invoices"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


def _model(index: int) -> type[SQLModel]:
    return type(
        f"PqcLedger{index}",
        (SQLModel,),
        {
            "__tablename__": f"pqc_ledger_{index}",
            "__annotations__": {"id": int | None, "label": str},
            "id": Field(default=None, primary_key=True),
            "label": "",
        },
        table=True,
    )


#: With ``Invoice``, 20 registered models: the sidebar and the guards check each of them.
OTHER_MODELS = [_model(index) for index in range(MODEL_COUNT - 1)]
MODELS = [Invoice, *OTHER_MODELS]


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
async def engine(tmp_path: Any) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pqc.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def ids(engine: AsyncEngine) -> dict[str, int]:
    """Seed ``staff`` (group Clerks: view/change/delete on every model) and ``root``."""
    await PermissionSyncService(engine=engine).sync_permissions(
        [(model.__name__.lower(), None) for model in MODELS]
    )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        staff = User(username="staff", email="staff@x.io", password_hash=hash_password(PASSWORD))
        root = User(
            username="root",
            email="root@x.io",
            password_hash=hash_password(PASSWORD),
            is_superuser=True,
        )
        clerks = Group(name="Clerks")
        session.add_all([staff, root, clerks])
        await session.commit()
        rows = (await session.execute(select(Permission.codename, Permission.id))).all()
        for codename, permission_id in rows:
            if not codename.startswith("add_"):
                session.add(GroupPermission(group_id=clerks.id, permission_id=permission_id))
        session.add(UserGroup(user_id=staff.id, group_id=clerks.id))
        await session.commit()
        return {"staff": int(staff.id or 0), "root": int(root.id or 0), "clerks": int(clerks.id)}


@pytest.fixture
def app(engine: AsyncEngine, ids: dict[str, int]) -> FastAPI:
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )
    for model in MODELS:
        site.register(model)
    admin.mount("/admin")
    return app


@asynccontextmanager
async def _client(app: FastAPI, username: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with_csrf(client, SECRET)
        await client.post("/admin/login", data={"username": username, "password": PASSWORD})
        yield client


def _record_statements(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    return statements


def _permission_statements(statements: list[str]) -> list[str]:
    return [sql for sql in statements if any(table in sql for table in PERMISSION_TABLES)]


async def _load(engine: AsyncEngine, user_id: int) -> Any:
    """Load a user the way a request does: a new object from the auth backend."""
    request = SimpleNamespace(session={"user_id": user_id})
    user = await SessionAuthBackend(engine=engine).get_current_user(request)  # type: ignore[arg-type]
    assert user is not None
    return user


# ── story scenarios ────────────────────────────────────────────────────────────


async def test_many_checks_in_one_request_cost_two_queries(app, engine) -> None:
    """
    Scenario: many checks in one request cost two queries
      Given a staff user with a group permission and 20 registered models
      When  GET /admin/invoice/
      Then  the permission step runs 2 SQL statements in total
    """
    # Given
    async with _client(app, "staff") as client:
        statements = _record_statements(engine)

        # When
        response = await client.get(LIST_URL)

    # Then
    assert response.status_code == 200
    assert len(_permission_statements(statements)) == 2


async def test_a_new_request_sees_a_changed_permission(app, engine, ids) -> None:
    """
    Scenario: a new request sees a changed permission
      Given a staff user whose permission was just revoked
      When  the next request arrives
      Then  the revoked permission is denied
    """
    async with _client(app, "staff") as client:
        assert (await client.get(LIST_URL)).status_code == 200

        # Given
        async with AsyncSession(engine) as session:
            await session.execute(
                delete(GroupPermission).where(GroupPermission.group_id == ids["clerks"])  # type: ignore[arg-type]
            )
            await session.commit()

        # When
        response = await client.get(LIST_URL)

    # Then
    assert response.status_code == 403


async def test_a_new_request_sees_a_granted_permission(app, engine, ids) -> None:
    """
    Scenario: a new request sees a granted permission
      Given a staff user who was just granted add_invoice directly
      When  the next request arrives
      Then  the granted permission is honoured
    """
    async with _client(app, "staff") as client:
        assert (await client.get("/admin/invoice/create")).status_code == 403

        # Given
        async with AsyncSession(engine) as session:
            stmt = select(Permission.id).where(Permission.codename == "add_invoice")
            permission_id = (await session.execute(stmt)).scalar_one()
            session.add(UserPermission(user_id=ids["staff"], permission_id=permission_id))
            await session.commit()

        # When
        response = await client.get("/admin/invoice/create")

    # Then
    assert response.status_code == 200


async def test_a_superuser_costs_nothing(app, engine) -> None:
    """
    Scenario: a superuser costs nothing
      Given a signed-in superuser
      When  GET /admin/invoice/
      Then  the permission step runs 0 SQL statements
    """
    # Given
    async with _client(app, "root") as client:
        statements = _record_statements(engine)

        # When
        response = await client.get(LIST_URL)

    # Then
    assert response.status_code == 200
    assert _permission_statements(statements) == []


# ── the set lives on the user object ───────────────────────────────────────────


async def test_both_sources_are_read_once_per_user_object(engine, ids) -> None:
    """
    Scenario: both sources are read once per user object
      Given a staff user loaded for one request
      When  the full set is read and then 30 single permissions are checked
      Then  2 SQL statements ran, and a second user object reads them again
    """
    # Given
    checker = ModelPermissionChecker(engine=engine)
    user = await _load(engine, ids["staff"])
    statements = _record_statements(engine)

    # When
    held = await checker.get_user_permissions(user)
    answers = [await checker.has_permission(user, f"view_pqcledger{i}") for i in range(15)]
    answers += [await checker.has_permission(user, f"add_pqcledger{i}") for i in range(15)]

    # Then
    assert "view_invoice" in held
    assert answers == [True] * 15 + [False] * 15
    assert len(statements) == 2

    # And a new object for the same user (the next request) starts over
    await checker.has_permission(await _load(engine, ids["staff"]), "view_invoice")
    assert len(_permission_statements(statements)) == 4


async def test_returned_set_is_the_callers_own_copy(engine, ids) -> None:
    """
    Scenario: the returned set is the caller's own copy
      Given a staff user whose permissions were read once
      When  the caller adds a codename to the returned set
      Then  later checks do not see it
    """
    # Given
    checker = ModelPermissionChecker(engine=engine)
    user = await _load(engine, ids["staff"])
    held = await checker.get_user_permissions(user)

    # When
    held.add("add_invoice")

    # Then
    assert await checker.has_permission(user, "add_invoice") is False
    assert "add_invoice" not in await checker.get_user_permissions(user)


async def test_forgetting_makes_the_same_object_read_again(engine, ids) -> None:
    """
    Scenario: forgetting makes the same user object read again
      Given a staff user whose permissions were read, then revoked in the database
      When  the set remembered on the object is forgotten
      Then  the next check reads the database and denies the permission
    """
    # Given
    checker = ModelPermissionChecker(engine=engine)
    user = await _load(engine, ids["staff"])
    assert await checker.has_permission(user, "view_invoice") is True
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(GroupPermission).where(GroupPermission.group_id == ids["clerks"])  # type: ignore[arg-type]
        )
        await session.commit()
    assert await checker.has_permission(user, "view_invoice") is True

    # When
    forget_user_permissions(user)

    # Then
    assert await checker.has_permission(user, "view_invoice") is False


async def test_two_checkers_do_not_share_a_set(engine, ids, tmp_path) -> None:
    """
    Scenario: two checkers do not share a set
      Given one user object and a second checker on a database without grants
      When  both checkers are asked about the same permission
      Then  each answers from its own database
    """
    # Given
    other_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'other.db'}")
    async with other_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    user = await _load(engine, ids["staff"])

    # When
    first = await ModelPermissionChecker(engine=engine).has_permission(user, "view_invoice")
    second = await ModelPermissionChecker(engine=other_engine).has_permission(user, "view_invoice")
    await other_engine.dispose()

    # Then
    assert first is True
    assert second is False


async def test_a_user_that_is_not_an_orm_object_is_read_on_every_check(engine, ids) -> None:
    """
    Scenario: a user that is not an ORM object is read on every check
      Given a plain object standing in for the staff user
      When  a permission is checked twice and then forgotten
      Then  each check reads the database (4 SQL statements) and forgetting is a no-op
    """
    # Given
    checker = ModelPermissionChecker(engine=engine)
    user: Any = SimpleNamespace(id=ids["staff"], is_superuser=False)
    statements = _record_statements(engine)

    # When
    first = await checker.has_permission(user, "view_invoice")
    second = await checker.has_permission(user, "view_invoice")
    forget_user_permissions(user)

    # Then
    assert (first, second) == (True, True)
    assert len(statements) == 4


async def test_matrix_save_forgets_the_set_of_the_operator(app, engine, ids, monkeypatch) -> None:
    """
    Scenario: the permissions matrix save forgets the operator's remembered set
      Given a staff user who holds change_groups_permissions and belongs to Clerks
      When  they save a matrix diff for Clerks
      Then  the set remembered on that request's user object is dropped
    """
    # Given
    codename = "change_groups_permissions"
    await PermissionSyncService(engine=engine).sync_codenames(
        [(codename, "Can change group permissions", None)]
    )
    async with AsyncSession(engine) as session:
        permission_id = (
            await session.execute(select(Permission.id).where(Permission.codename == codename))
        ).scalar_one()
        session.add(UserPermission(user_id=ids["staff"], permission_id=permission_id))
        await session.commit()
    forgotten: list[Any] = []

    def spy(user: Any) -> None:
        forgotten.append(user)
        forget_user_permissions(user)

    monkeypatch.setattr(matrix_views, "forget_user_permissions", spy)

    # When
    async with _client(app, "staff") as client:
        response = await client.post(
            "/admin/permissions-matrix/save",
            json={
                "group_id": ids["clerks"],
                "version": 0,
                "changes": [{"model": "invoice", "codename": "view_invoice", "granted": False}],
            },
            headers={"hx-request": "true"},
        )

    # Then
    assert response.status_code == 200
    assert [user.id for user in forgotten] == [ids["staff"]]


async def test_a_live_socket_sees_a_revoked_permission_on_the_next_subscribe(engine, ids) -> None:
    """
    Scenario: a live socket sees a revoked permission on the next subscribe
      Given one user object kept by a WebSocket that already followed invoice
      When  the permission is revoked and the socket subscribes again
      Then  the subscription is denied
    """
    # Given
    admin = Admin(
        app=FastAPI(),
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET),
        permission_checker=ModelPermissionChecker(engine=engine),
    )
    admin._notification_models = {"invoice"}
    user = await _load(engine, ids["staff"])
    assert await admin._authorize_notification_subscription(user, "invoice") is True

    # When
    async with AsyncSession(engine) as session:
        await session.execute(
            delete(GroupPermission).where(GroupPermission.group_id == ids["clerks"])  # type: ignore[arg-type]
        )
        await session.commit()

    # Then
    assert await admin._authorize_notification_subscription(user, "invoice") is False
