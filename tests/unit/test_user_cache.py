"""Opt-in per-worker user cache (st-perf-04)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

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
from hyperadmin.auth.user_cache import (
    CachedUser,
    UserCache,
    clone_user,
    invalidate_all,
    invalidate_user,
)
from hyperadmin.core.settings import HyperAdminSettings

pytestmark = pytest.mark.anyio


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _make(cls: Any) -> Any:
    # The exact built-in type is what the cache accepts; behaviour is patched on the instance.
    return cls(session_factory=lambda: None)


def _backend(user: Any = None, *, load: Any = None) -> Any:
    """The built-in backend with a canned (or computed) user and a ``loads`` counter."""
    backend: Any = _make(SessionAuthBackend)
    backend.loads = 0

    async def get_current_user(request: Any) -> Any:
        backend.loads += 1
        return await load(request) if load else user

    backend.get_current_user = get_current_user
    return backend


def _checker() -> Any:
    checker: Any = _make(ModelPermissionChecker)
    checker.calls = 0

    async def get_user_permissions(user: Any) -> set[str]:
        checker.calls += 1
        return {"view_x"}

    checker.get_user_permissions = get_user_permissions
    return checker


class _Inner:
    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def _scope(session: dict[str, Any] | None) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/admin/",
        "raw_path": b"/admin/",
        "root_path": "",
        "query_string": b"",
        "headers": [],
    }
    if session is not None:
        scope["session"] = session
    return scope


async def _receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _call(mw: Any, session: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = _scope(session)
    await mw(scope, _receive, send)
    return sent[0]["status"], scope


def _user(uid: int = 1) -> Any:
    return User(
        id=uid,
        username=f"u{uid}",
        email=f"u{uid}@x.io",
        password_hash="h",
        is_superuser=False,
        is_active=True,
    )


async def test_repeated_requests_load_the_user_once() -> None:
    """
    Scenario: repeated requests load the user once
      Given user_cache_ttl is 5
      When  100 requests arrive in one second from one session
      Then  the user is loaded once
    """
    backend, checker, clock = _backend(_user()), _checker(), _Clock()
    mw = AuthenticationMiddleware(
        _Inner(), backend, permission_checker=checker, user_cache_ttl=5, clock=clock
    )

    for _ in range(100):
        clock.now += 0.01
        status, scope = await _call(mw, {"user_id": 1})
        assert status == 200
        assert scope["state"]["user_permissions"] == frozenset({"view_x"})

    assert backend.loads == 1
    assert checker.calls == 1


async def test_deactivated_user_is_locked_out_after_the_ttl() -> None:
    """
    Scenario: a deactivated user is locked out after the TTL
      Given the user is cached and then deactivated
      When  the TTL has passed and the next request arrives
      Then  the response redirects to login
    """
    user, clock = _user(), _Clock()
    mw = AuthenticationMiddleware(_Inner(), _backend(user), user_cache_ttl=5, clock=clock)
    assert (await _call(mw, {"user_id": 1}))[0] == 200

    user.is_active = False
    clock.now = 4.9
    assert (await _call(mw, {"user_id": 1}))[0] == 200  # still inside the TTL window
    clock.now = 5.0
    status, _ = await _call(mw, {"user_id": 1})

    assert status == 302


async def test_ttl_zero_keeps_todays_behaviour() -> None:
    """
    Scenario: TTL 0 keeps today's behaviour
      Given user_cache_ttl is 0
      When  two requests arrive
      Then  the user is loaded twice
    """
    backend, checker = _backend(_user()), _checker()
    mw = AuthenticationMiddleware(_Inner(), backend, permission_checker=checker)

    await _call(mw, {"user_id": 1})
    await _call(mw, {"user_id": 1})

    assert backend.loads == 2
    assert checker.calls == 2


async def test_inactive_user_is_rejected_whatever_the_ttl() -> None:
    """
    Scenario: an inactive user never gets in, cache or not
      Given the backend returns an inactive user
      When  a request arrives with user_cache_ttl 0, then with 5
      Then  both redirect to login
    """
    user = _user()
    user.is_active = False

    for ttl in (0, 5):
        mw = AuthenticationMiddleware(_Inner(), _backend(user), user_cache_ttl=ttl)
        assert (await _call(mw, {"user_id": 1}))[0] == 302


async def test_entries_are_keyed_by_session_user_id() -> None:
    """
    Scenario: one user's entry is never served to another
      Given user 1 is cached
      When  a request arrives from a session of user 2
      Then  user 2 is loaded and its own user is exposed
    """

    async def per_session(request: Any) -> Any:
        return _user(request.session["user_id"])

    backend = _backend(load=per_session)
    mw = AuthenticationMiddleware(_Inner(), backend, user_cache_ttl=5, clock=_Clock())

    _, first = await _call(mw, {"user_id": 1})
    _, second = await _call(mw, {"user_id": 2})
    _, again = await _call(mw, {"user_id": 1})

    assert (first["state"]["user"].id, second["state"]["user"].id) == (1, 2)
    assert again["state"]["user"].id == 1
    assert backend.loads == 2


@pytest.mark.parametrize("session", [None, {}, {"user_id": "7"}, {"user_id": uuid.UUID(int=7)}])
async def test_requests_without_a_usable_session_user_id_bypass_the_cache(
    session: dict[str, Any] | None,
) -> None:
    """
    Scenario: no session user id bypasses the cache
      Given user_cache_ttl is 5 and the session carries no integer user id
      When  two requests arrive
      Then  the backend resolves the user both times
    """
    backend = _backend(_user())
    mw = AuthenticationMiddleware(_Inner(), backend, user_cache_ttl=5, clock=_Clock())

    await _call(mw, session)
    await _call(mw, session)

    assert backend.loads == 2


async def test_anonymous_result_is_not_cached() -> None:
    """
    Scenario: a missing user is never cached
      Given the session user no longer exists
      When  two requests arrive
      Then  both redirect to login and the backend is asked each time
    """
    backend = _backend(None)
    mw = AuthenticationMiddleware(_Inner(), backend, user_cache_ttl=5, clock=_Clock())

    assert (await _call(mw, {"user_id": 3}))[0] == 302
    assert (await _call(mw, {"user_id": 3}))[0] == 302
    assert backend.loads == 2


def test_cache_is_bounded_and_expires() -> None:
    """
    Scenario: the cache is bounded and entries expire
      Given a cache of two entries with a 5 s TTL
      When  three keys are stored and time passes
      Then  the oldest key is evicted and expired keys disappear
    """
    clock = _Clock()
    cache = UserCache(5, clock=clock, max_entries=2)
    for key in (1, 2, 3):
        cache.set(key, CachedUser(key, None), 0)
    assert cache.get(1) is None
    assert cache.get(3) == CachedUser(3, None)
    cache.set(2, CachedUser(2, None), 0)  # re-set refreshes the entry
    clock.now = 5
    assert cache.get(2) is None


def test_invalidate_user_and_all() -> None:
    """
    Scenario: invalidation drops entries on this worker
      Given two cached users
      When  one user, then everyone, is invalidated
      Then  only that user, then all entries, are gone
    """
    cache = UserCache(5)
    cache.set(1, CachedUser(1, None), 0)
    cache.set(2, CachedUser(2, None), 0)
    invalidate_user(1)
    assert cache.get(1) is None
    assert cache.get(2) is not None
    invalidate_all()
    assert cache.get(2) is None


# -- write-path invalidation through a real database ---------------------------------


@pytest.fixture
async def factory() -> AsyncIterator[Any]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


def _row(name: str) -> User:
    return User(username=name, email=f"{name}@x.io", password_hash="h")


async def _commit(factory: Any, *objs: Any, delete: bool = False) -> None:
    async with factory() as session:
        for obj in objs:
            if delete:
                await session.delete(await session.merge(obj))
            else:
                session.add(obj)
        await session.commit()


async def test_user_write_invalidates_only_that_user(factory: Any) -> None:
    """
    Scenario: a user write drops that user's entry on this worker
      Given users a and b are cached
      When  user a is updated and committed
      Then  a's entry is gone and b's remains
    """
    a, b = _row("a"), _row("b")
    await _commit(factory, a, b)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)
    cache.set(b.id, CachedUser(b, None), cache.generation)

    a.is_active = False
    await _commit(factory, a)

    assert cache.get(a.id) is None
    assert cache.get(b.id) is not None


async def test_user_delete_invalidates_entry(factory: Any) -> None:
    """
    Scenario: deleting a user drops the entry
      Given a user is cached
      When  the user is deleted
      Then  the entry is gone
    """
    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)

    await _commit(factory, a, delete=True)

    assert cache.get(a.id) is None


async def test_group_assignment_invalidates_that_user(factory: Any) -> None:
    """
    Scenario: assigning a group drops the user's entry
      Given a user and a group exist and the user is cached
      When  a UserGroup row is committed
      Then  the user's entry is gone
    """
    a, g = _row("a"), Group(name="g")
    await _commit(factory, a, g)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)

    await _commit(factory, UserGroup(user_id=a.id, group_id=g.id))

    assert cache.get(a.id) is None


async def test_group_permission_change_invalidates_everyone(factory: Any) -> None:
    """
    Scenario: changing a group's permissions drops every entry
      Given two cached users
      When  a GroupPermission row is committed
      Then  all entries are gone
    """
    a, b, g, p = _row("a"), _row("b"), Group(name="g"), Permission(codename="c", name="C")
    await _commit(factory, a, b, g, p)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)
    cache.set(b.id, CachedUser(b, None), cache.generation)

    await _commit(factory, GroupPermission(group_id=g.id, permission_id=p.id))

    assert cache.get(a.id) is None
    assert cache.get(b.id) is None


async def test_rolled_back_write_does_not_invalidate(factory: Any) -> None:
    """
    Scenario: a rolled-back write leaves the cache alone
      Given a user is cached
      When  the user is changed, flushed and rolled back
      Then  the entry remains
    """
    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)

    async with factory() as session:
        row = await session.get(User, a.id)
        assert row is not None
        row.is_active = False
        await session.flush()
        await session.rollback()
        await session.commit()

    assert cache.get(a.id) is not None


async def test_empty_commit_leaves_entries(factory: Any) -> None:
    """
    Scenario: a commit that wrote nothing keeps the cache
      Given a user is cached
      When  a session commits without changes
      Then  the entry remains
    """
    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)

    async with factory() as session:
        await session.commit()

    assert cache.get(a.id) is not None


def test_setting_default_env_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: user_cache_ttl is off by default and read from the environment
      Given no HYPERADMIN_USER_CACHE_TTL
      When  settings are built, then built again with the variable set
      Then  the default is 0, the variable is honoured and negatives and values above 60 are rejected
    """
    monkeypatch.delenv("HYPERADMIN_USER_CACHE_TTL", raising=False)
    assert HyperAdminSettings().user_cache_ttl == 0
    monkeypatch.setenv("HYPERADMIN_USER_CACHE_TTL", "5")
    assert HyperAdminSettings().user_cache_ttl == 5
    with pytest.raises(ValueError, match="greater than or equal"):
        HyperAdminSettings(user_cache_ttl=-1)
    with pytest.raises(ValueError, match="less than or equal"):
        HyperAdminSettings(user_cache_ttl=61)


def test_fill_that_started_before_an_invalidation_is_dropped() -> None:
    """
    Scenario: a fill racing an invalidation is dropped
      Given a request read the cache generation and is still loading its user
      When  a write invalidates that user and the request then stores its result
      Then  the stale value is not cached
    """
    cache = UserCache(5)
    started = cache.generation

    invalidate_user(1)
    cache.set(1, CachedUser(1, None), started)

    assert cache.get(1) is None
    cache.set(1, CachedUser(1, None), cache.generation)
    assert cache.get(1) is not None
    invalidate_all()
    cache.set(2, CachedUser(2, None), started)
    assert cache.get(2) is None


async def test_invalidation_between_load_and_store_leaves_nothing_cached() -> None:
    """
    Scenario: a revocation committed mid-request is not cached
      Given a cache miss is loading the user
      When  invalidate_user runs before the request finishes
      Then  the next request loads the user again
    """

    async def racy(request: Any) -> Any:
        invalidate_user(1)
        return _user()

    backend = _backend(load=racy)
    mw = AuthenticationMiddleware(_Inner(), backend, user_cache_ttl=5, clock=_Clock())

    await _call(mw, {"user_id": 1})
    await _call(mw, {"user_id": 1})

    assert backend.loads == 2


async def test_cache_hits_hand_out_private_copies() -> None:
    """
    Scenario: one request cannot change the user another is served
      Given a user is cached
      When  a request mutates request.state.user
      Then  the next request sees the original values
    """
    mw = AuthenticationMiddleware(_Inner(), _backend(_user()), user_cache_ttl=5, clock=_Clock())
    await _call(mw, {"user_id": 1})

    _, hit = await _call(mw, {"user_id": 1})
    hit["state"]["user"].is_superuser = True
    _, again = await _call(mw, {"user_id": 1})

    assert again["state"]["user"].is_superuser is False
    assert again["state"]["user"] is not hit["state"]["user"]
    assert again["state"]["user"].username == "u1"


async def test_unmapped_users_are_not_cached() -> None:
    """
    Scenario: a user that is not an ORM row is loaded every time
      Given the backend returns a plain object
      When  two requests arrive
      Then  the backend is asked both times
    """
    backend = _backend(SimpleNamespace(id=1, username="x", is_superuser=False, is_active=True))
    mw = AuthenticationMiddleware(_Inner(), backend, user_cache_ttl=5, clock=_Clock())

    await _call(mw, {"user_id": 1})
    await _call(mw, {"user_id": 1})

    assert backend.loads == 2
    assert clone_user(object()) is None


async def test_custom_backend_or_checker_disables_the_cache(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a custom backend or permission checker is never cached
      Given user_cache_ttl is 5 and the backend is not the built-in one
      When  the middleware is built and two requests arrive
      Then  a warning is logged and the backend is asked both times
    """

    class _Custom:
        loads = 0

        async def get_current_user(self, request: Any) -> Any:
            self.loads += 1
            return _user()

    custom = _Custom()
    with caplog.at_level(logging.WARNING):
        mw = AuthenticationMiddleware(_Inner(), custom, user_cache_ttl=5, clock=_Clock())
        AuthenticationMiddleware(
            _Inner(), _backend(_user()), permission_checker=object(), user_cache_ttl=5
        )
    await _call(mw, {"user_id": 1})
    await _call(mw, {"user_id": 1})

    assert custom.loads == 2
    assert caplog.text.count("user_cache_ttl is ignored") == 2


@pytest.mark.parametrize("kind", ["update", "delete", "insert"])
async def test_bulk_statement_on_an_auth_table_invalidates_everyone(
    factory: Any, kind: str
) -> None:
    """
    Scenario: a bulk statement on an auth table drops every entry
      Given a user is cached
      When  a bulk UPDATE, DELETE or INSERT on an auth table is committed
      Then  the entry is gone
    """
    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)
    statement = {
        "update": update(User).where(User.id == a.id).values(is_active=False),
        "delete": delete(UserPermission),
        "insert": insert(Group).values(name="g"),
    }[kind]

    async with factory() as session:
        await session.execute(statement)
        await session.commit()

    assert cache.get(a.id) is None


async def test_bulk_statement_on_another_table_keeps_entries(factory: Any) -> None:
    """
    Scenario: a SELECT or a bulk write elsewhere keeps the cache
      Given a user is cached
      When  a SELECT runs and a bulk statement hits a non-auth table
      Then  the entry remains
    """
    from sqlalchemy import Column, Integer, MetaData, Table, select

    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)
    other = Table("elsewhere", MetaData(), Column("id", Integer, primary_key=True))

    async with factory() as session:
        await session.execute(select(User))
        await session.run_sync(lambda s: other.create(s.connection()))
        await session.execute(insert(other).values(id=1))
        await session.commit()

    assert cache.get(a.id) is not None


async def test_new_user_without_an_id_does_not_invalidate_by_none(factory: Any) -> None:
    """
    Scenario: creating a user does not touch other entries
      Given a user is cached
      When  another user is created and committed
      Then  the first entry remains
    """
    a = _row("a")
    await _commit(factory, a)
    cache = UserCache(60)
    cache.set(a.id, CachedUser(a, None), cache.generation)

    await _commit(factory, _row("b"))

    assert cache.get(a.id) is not None
