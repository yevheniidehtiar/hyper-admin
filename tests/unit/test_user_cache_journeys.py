"""User-cache journeys against a real database and the real auth collaborators (st-perf-04).

The E2E journeys in ``tests/e2e/test_user_cache_journeys.py`` cover the browser side; these cover
what needs a hand on the clock or a pause inside a request: staleness windows, an in-flight
request racing a commit, and the exact SQL a request costs.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, event, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.middleware import AuthenticationMiddleware
from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.auth.permissions import ModelPermissionChecker
from hyperadmin.auth.session import SessionAuthBackend

pytestmark = pytest.mark.anyio

TTL = 5


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _Recorder:
    """Inner ASGI app: answers 200 and keeps what the middleware put on ``request.state``."""

    def __init__(self) -> None:
        self.users: list[Any] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.users.append(scope["state"]["user"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'journeys.db'}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def app() -> _Recorder:
    return _Recorder()


@pytest.fixture
def middleware(engine: AsyncEngine, clock: _Clock, app: _Recorder) -> AuthenticationMiddleware:
    return AuthenticationMiddleware(
        app,
        SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        user_cache_ttl=TTL,
        clock=clock,
    )


@pytest.fixture
async def ids(engine: AsyncEngine) -> dict[str, int]:
    """Seed ``ann`` (direct view_x), ``bob`` (group Staff: view_y) and ``root`` (superuser)."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        users = {
            name: User(
                username=name,
                email=f"{name}@x.io",
                password_hash=hash_password("pw"),
                is_superuser=name == "root",
            )
            for name in ("ann", "bob", "root")
        }
        perms = {c: Permission(codename=c, name=c) for c in ("view_x", "view_y")}
        staff = Group(name="Staff")
        session.add_all([*users.values(), *perms.values(), staff])
        await session.commit()
        session.add(UserPermission(user_id=users["ann"].id, permission_id=perms["view_x"].id))
        session.add(GroupPermission(group_id=staff.id, permission_id=perms["view_y"].id))
        session.add(UserGroup(user_id=users["bob"].id, group_id=staff.id))
        await session.commit()
        return {name: int(user.id or 0) for name, user in users.items()}


async def _request(mw: AuthenticationMiddleware, user_id: int) -> tuple[int, dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/admin/",
        "raw_path": b"/admin/",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "session": {"user_id": user_id},
    }
    await mw(scope, receive, send)
    return sent[0]["status"], scope


async def _permissions(mw: AuthenticationMiddleware, user_id: int) -> frozenset[str] | None:
    status, scope = await _request(mw, user_id)
    assert status == 200
    return scope["state"]["user_permissions"]


def _record_statements(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        statements.append(statement)

    return statements


async def test_write_from_another_worker_is_served_stale_until_the_ttl(
    engine: AsyncEngine, middleware: AuthenticationMiddleware, clock: _Clock, ids: dict[str, int]
) -> None:
    """
    Scenario: a write no session listener sees is bounded by the TTL
      Given ann is cached with view_x
      When  her grant is deleted and she is deactivated on a bare connection (another worker)
      Then  requests inside the TTL still pass with the old permissions
      And   the first request after the TTL sees the new state
    """
    # Given ann is cached with view_x
    assert await _permissions(middleware, ids["ann"]) == {"view_x"}

    # When her grant is deleted on a bare connection
    async with engine.begin() as conn:
        await conn.execute(delete(UserPermission.__table__))  # type: ignore[arg-type]

    # Then requests inside the TTL still pass with the old permissions
    clock.now = TTL - 0.1
    assert await _permissions(middleware, ids["ann"]) == {"view_x"}
    # And the first request after the TTL sees the new state
    clock.now = TTL
    assert await _permissions(middleware, ids["ann"]) == frozenset()

    # When she is deactivated on a bare connection
    async with engine.begin() as conn:
        await conn.execute(update(User.__table__).values(is_active=False))  # type: ignore[arg-type]
    clock.now = TTL + 1
    assert (await _request(middleware, ids["ann"]))[0] == 200
    clock.now = 2 * TTL
    # Then the next request after the TTL is redirected to login
    assert (await _request(middleware, ids["ann"]))[0] == 302


async def test_writes_on_this_worker_show_on_the_next_request(
    engine: AsyncEngine, middleware: AuthenticationMiddleware, ids: dict[str, int]
) -> None:
    """
    Scenario: same-worker writes need no clock
      Given ann (direct grant), bob (group grant) and root (superuser) are cached
      When  ann's grant is deleted, bob leaves his group and root loses the flag, each committed
      Then  the very next request of each sees the new permissions, with the clock unmoved
    """
    # Given ann, bob and root are cached
    assert await _permissions(middleware, ids["ann"]) == {"view_x"}
    assert await _permissions(middleware, ids["bob"]) == {"view_y"}
    assert await _permissions(middleware, ids["root"]) is None

    async with AsyncSession(engine) as session:
        # When ann's grant is deleted (ORM), bob leaves (bulk DELETE) and root loses the flag
        grant = (await session.execute(select(UserPermission))).scalars().one()
        await session.delete(grant)
        await session.execute(delete(UserGroup).where(UserGroup.user_id == ids["bob"]))  # type: ignore[arg-type]
        await session.execute(
            update(User).where(User.id == ids["root"]).values(is_superuser=False)  # type: ignore[arg-type]
        )
        await session.commit()

    # Then the very next request of each sees the new permissions
    assert await _permissions(middleware, ids["ann"]) == frozenset()
    assert await _permissions(middleware, ids["bob"]) == frozenset()
    assert await _permissions(middleware, ids["root"]) == frozenset()


async def test_alternating_users_each_get_their_own_identity_and_permissions(
    middleware: AuthenticationMiddleware, app: _Recorder, ids: dict[str, int]
) -> None:
    """
    Scenario: alternating cached users never leak
      Given ann, bob and root alternate over several requests
      When  every request completes
      Then  each sees its own username and permission set, from the cache after the first
    """
    expected = {"ann": {"view_x"}, "bob": {"view_y"}, "root": None}
    for _ in range(3):
        for name, perms in expected.items():
            assert await _permissions(middleware, ids[name]) == (
                None if perms is None else frozenset(perms)
            )
            assert app.users[-1].username == name


async def test_request_mutating_its_user_does_not_leak_to_others(
    middleware: AuthenticationMiddleware, app: _Recorder, ids: dict[str, int]
) -> None:
    """
    Scenario: a request that edits its user object changes nobody else's view
      Given ann is cached
      When  one request flips is_superuser and username on request.state.user
      Then  the next requests still get the stored values, each on its own object
    """
    await _request(middleware, ids["ann"])
    await _request(middleware, ids["ann"])
    app.users[-1].is_superuser = True
    app.users[-1].username = "mallory"

    await _request(middleware, ids["ann"])
    await _request(middleware, ids["ann"])

    assert (app.users[-1].username, app.users[-1].is_superuser) == ("ann", False)
    assert app.users[-1] is not app.users[-2]


async def test_commit_during_a_cache_miss_is_never_cached(
    engine: AsyncEngine, clock: _Clock, app: _Recorder, ids: dict[str, int]
) -> None:
    """
    Scenario: a revocation committed while a request is loading is not cached
      Given a request is on a cache miss, paused after loading ann's permissions
      When  ann's grant is deleted and committed, then the request finishes
      Then  the next request sees no permissions, not the stale set the paused one loaded
    """
    loaded, release = asyncio.Event(), asyncio.Event()
    checker = ModelPermissionChecker(engine=engine)
    original = checker.get_user_permissions

    async def paused(user: Any) -> set[str]:
        result = await original(user)
        loaded.set()
        await release.wait()
        return result

    checker.get_user_permissions = paused  # type: ignore[method-assign]
    mw = AuthenticationMiddleware(
        app,
        SessionAuthBackend(engine=engine),
        permission_checker=checker,
        user_cache_ttl=TTL,
        clock=clock,
    )

    # Given a request is on a cache miss, paused after loading ann's permissions
    in_flight = asyncio.create_task(_request(mw, ids["ann"]))
    await loaded.wait()

    # When ann's grant is deleted and committed, then the request finishes
    async with AsyncSession(engine) as session:
        await session.delete((await session.execute(select(UserPermission))).scalars().one())
        await session.commit()
    release.set()
    _, scope = await in_flight
    assert scope["state"]["user_permissions"] == {"view_x"}  # it answered from what it loaded

    # Then the next request sees no permissions
    checker.get_user_permissions = original  # type: ignore[method-assign]
    assert await _permissions(mw, ids["ann"]) == frozenset()


async def test_requests_inside_the_ttl_run_no_auth_sql(
    engine: AsyncEngine, middleware: AuthenticationMiddleware, clock: _Clock, ids: dict[str, int]
) -> None:
    """
    Scenario: the auth query runs once per TTL window
      Given nothing is cached
      When  ten requests arrive inside the TTL, then ten more after it
      Then  each window costs the user query and both permission queries once, 3 statements
    """
    statements = _record_statements(engine)

    # When ten requests arrive inside the TTL
    for _ in range(10):
        clock.now += 0.1
        await _request(middleware, ids["bob"])
    # Then the first one cost the user and two permission queries, the rest nothing
    assert len(statements) == 3

    # When ten more arrive after it
    clock.now += TTL
    for _ in range(10):
        clock.now += 0.1
        await _request(middleware, ids["bob"])
    # Then the new window costs the same 3 statements
    assert len(statements) == 6
