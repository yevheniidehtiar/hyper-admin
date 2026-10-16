"""Unit tests for ``hyperadmin.core.lifecycle`` and the ``Admin`` lifecycle API.

Spec: ``docs/specs/bring-your-own-app.md`` section C.2.
Story: ``.meta/epics/epic-v058-bring-your-own-app/stories/
featcore-lifecycle-with-opt-in-create-tables-startup-shutdow.md``.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel, select

from hyperadmin.auth.models import Permission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.lifecycle import Lifecycle, StartupGuardMiddleware, StartupUnavailableError
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


async def _table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return set(await conn.run_sync(lambda sync: inspect(sync).get_table_names()))


# ---------------------------------------------------------------------------
# Lifecycle — pure orchestration unit tests
# ---------------------------------------------------------------------------


def _make_lifecycle(**kwargs: Any) -> tuple[Lifecycle, AsyncMock, AsyncMock, AsyncMock]:
    create_tables = AsyncMock()
    sync_permissions = AsyncMock()
    drain = AsyncMock()
    lifecycle = Lifecycle(
        create_tables=create_tables,
        sync_permissions=sync_permissions,
        drain=drain,
        **kwargs,
    )
    return lifecycle, create_tables, sync_permissions, drain


@pytest.mark.anyio
async def test_startup_creates_tables_then_syncs_permissions() -> None:
    """
    Scenario: startup creates tables then syncs permissions, in order
      Given a Lifecycle with create_tables and sync_permissions callables
      When  startup() runs
      Then  create_tables is awaited before sync_permissions
    """
    order: list[str] = []
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = lambda: order.append("create_tables")
    sync_permissions.side_effect = lambda: order.append("sync_permissions")

    await lifecycle.startup()

    assert order == ["create_tables", "sync_permissions"]
    assert lifecycle.started is True


@pytest.mark.anyio
async def test_startup_is_idempotent() -> None:
    """
    Scenario: startup is idempotent
      Given a Lifecycle that already completed startup()
      When  startup() runs again
      Then  create_tables and sync_permissions are not called again
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)

    await lifecycle.startup()
    await lifecycle.startup()
    await lifecycle.ensure_started()

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()


@pytest.mark.anyio
async def test_concurrent_startup_calls_run_the_work_exactly_once() -> None:
    """
    Scenario: concurrent startup callers race for the lock, work runs once
      Given several concurrent calls to startup()/ensure_started()
      When  they all run before the first one finishes
      Then  create_tables and sync_permissions are each awaited exactly once
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)

    async def _slow_create_tables() -> None:
        await asyncio.sleep(0.01)

    create_tables.side_effect = _slow_create_tables

    await asyncio.gather(
        lifecycle.startup(),
        lifecycle.ensure_started(),
        lifecycle.startup(),
    )

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()


@pytest.mark.anyio
async def test_startup_failure_is_not_cached_and_the_next_call_retries() -> None:
    """
    Scenario: a startup failure is not cached, so the next call retries
      Given create_tables raises on the first call and succeeds on the second
      When  startup() is called twice
      Then  the first call raises, started stays False, and the second call
        succeeds and completes startup
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = [RuntimeError("db is down"), None]

    with pytest.raises(RuntimeError, match="db is down"):
        await lifecycle.startup()

    assert lifecycle.started is False

    await lifecycle.startup()

    assert lifecycle.started is True
    assert create_tables.await_count == 2
    sync_permissions.assert_awaited_once()


@pytest.mark.anyio
async def test_guard_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: a failure reached through the safety net is logged
      Given create_tables raises
      When  ensure_started() (the safety-net path) runs
      Then  the exception propagates AND is logged
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = RuntimeError("boom")

    with (
        caplog.at_level(logging.ERROR, logger="hyperadmin"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await lifecycle.ensure_started()

    assert any("startup failed" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_explicit_startup_failure_is_not_logged_by_lifecycle(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: an explicit startup() failure is left to the caller
      Given create_tables raises
      When  startup() (the explicit path, not the guard) runs
      Then  the exception propagates without Lifecycle logging it itself
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = RuntimeError("boom")

    with (
        caplog.at_level(logging.ERROR, logger="hyperadmin"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await lifecycle.startup()

    assert not any("startup failed" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_guard_warns_once_when_realtime_is_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: shutdown has no safety net — the guard warns when realtime is on
      Given realtime_enabled=True and startup was never called explicitly
      When  the first admin request reaches ensure_started()
      Then  a one-time WARNING tells the host to compose admin.lifespan()
    """
    lifecycle, _create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=True)

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        await lifecycle.ensure_started()
        await lifecycle.ensure_started()

    warnings = [r for r in caplog.records if "admin.lifespan()" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.anyio
async def test_guard_does_not_warn_when_realtime_is_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: no realtime, no warning
      Given realtime_enabled=False
      When  ensure_started() runs through the guard
      Then  no WARNING about admin.lifespan() is logged
    """
    lifecycle, _create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        await lifecycle.ensure_started()

    assert not any("admin.lifespan()" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_explicit_startup_never_warns_even_with_realtime_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: the explicit path never gets the "use lifespan()" warning
      Given realtime_enabled=True
      When  startup() (not ensure_started()) runs
      Then  no WARNING about admin.lifespan() is logged — the host already
        composed it, hence calling startup() explicitly
    """
    lifecycle, _create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=True)

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        await lifecycle.startup()

    assert not any("admin.lifespan()" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_shutdown_drains_connections() -> None:
    """
    Scenario: shutdown drains realtime connections
      Given a Lifecycle
      When  shutdown() runs
      Then  the drain callable is awaited
    """
    lifecycle, _create_tables, _sync_permissions, drain = _make_lifecycle(realtime_enabled=True)

    await lifecycle.shutdown()

    drain.assert_awaited_once()


@pytest.mark.anyio
async def test_lifespan_runs_startup_then_shutdown() -> None:
    """
    Scenario: lifespan() composes startup and shutdown around the host's own body
      Given a Lifecycle
      When  async with lifecycle.lifespan(): ... runs
      Then  startup runs before the body and shutdown runs after it
    """
    order: list[str] = []
    lifecycle, create_tables, _sync_permissions, drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = lambda: order.append("startup")
    drain.side_effect = lambda: order.append("shutdown")

    async with lifecycle.lifespan():
        order.append("body")

    assert order == ["startup", "body", "shutdown"]


@pytest.mark.anyio
async def test_lifespan_still_shuts_down_when_the_body_raises() -> None:
    """
    Scenario: shutdown still runs if the host's lifespan body raises
      Given a Lifecycle
      When  the body inside "async with lifecycle.lifespan():" raises
      Then  shutdown still runs and the original exception propagates
    """
    lifecycle, _create_tables, _sync_permissions, drain = _make_lifecycle(realtime_enabled=False)

    with pytest.raises(ValueError, match="body blew up"):
        async with lifecycle.lifespan():
            raise ValueError("body blew up")

    drain.assert_awaited_once()


# ---------------------------------------------------------------------------
# StartupGuardMiddleware — pure ASGI
# ---------------------------------------------------------------------------


class _FakeASGIApp:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.calls.append(scope)


@pytest.mark.anyio
async def test_guard_middleware_triggers_for_admin_paths() -> None:
    """
    Scenario: the guard middleware checks admin paths only
      Given StartupGuardMiddleware(admin_prefix="/admin")
      When  a request for /admin/ comes through
      Then  ensure_started() is called and the inner app still runs
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "http", "path": "/admin/"}, None, None)

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_ignores_other_host_paths() -> None:
    """
    Scenario: a host route outside the admin prefix is left untouched
      Given StartupGuardMiddleware(admin_prefix="/admin")
      When  a request for /health comes through
      Then  ensure_started() is never called, but the inner app still runs
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "http", "path": "/health"}, None, None)

    create_tables.assert_not_called()
    sync_permissions.assert_not_called()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_skips_non_http_scopes() -> None:
    """
    Scenario: non-HTTP ASGI scopes (e.g. lifespan) are passed through untouched
      Given StartupGuardMiddleware
      When  a "lifespan" scope comes through
      Then  ensure_started() is never called
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "lifespan", "path": "/admin/"}, None, None)

    create_tables.assert_not_called()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_is_a_cheap_no_op_once_started() -> None:
    """
    Scenario: once started, the guard is a single attribute read
      Given a Lifecycle that already completed startup()
      When  another admin request comes through
      Then  create_tables/sync_permissions are not awaited again
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    await lifecycle.startup()
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "http", "path": "/admin/"}, None, None)

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()


@pytest.mark.anyio
async def test_guard_middleware_matches_every_path_when_mounted_at_root() -> None:
    """
    Scenario: admin_prefix="/" matches every path, not just a literal "/"
      Given StartupGuardMiddleware(admin_prefix="/") (the admin mounted at
        the host's root)
      When  a request for /anything comes through
      Then  ensure_started() is called
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/")

    await middleware({"type": "http", "path": "/anything", "root_path": ""}, None, None)

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_does_not_match_overlapping_prefix() -> None:
    """
    Scenario: a host route that merely starts with admin_prefix is not matched
      Given StartupGuardMiddleware(admin_prefix="/admin")
      When  a request for /administrator comes through
      Then  ensure_started() is never called — matching is on whole path
        segments, not a raw string prefix
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "http", "path": "/administrator", "root_path": ""}, None, None)

    create_tables.assert_not_called()
    sync_permissions.assert_not_called()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_matches_when_host_app_is_itself_mounted() -> None:
    """
    Scenario: the guard still matches when the host app is mounted under its own prefix
      Given StartupGuardMiddleware(admin_prefix="/admin") composed under a host
        mounted at "/api" (so ASGI sets scope["root_path"]="/api" and
        scope["path"]="/api/admin/")
      When  a request for /api/admin/ comes through
      Then  ensure_started() is called — route-path matching strips the
        mount's root_path first
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware({"type": "http", "path": "/api/admin/", "root_path": "/api"}, None, None)

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_triggers_for_websocket_scopes() -> None:
    """
    Scenario: a websocket scope under the admin prefix also triggers the guard
      Given StartupGuardMiddleware(admin_prefix="/admin")
      When  a websocket connection to /admin/realtime/ws comes through
      Then  ensure_started() is called
    """
    lifecycle, create_tables, sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    await middleware(
        {"type": "websocket", "path": "/admin/realtime/ws", "root_path": ""}, None, None
    )

    create_tables.assert_awaited_once()
    sync_permissions.assert_awaited_once()
    assert len(inner.calls) == 1


@pytest.mark.anyio
async def test_guard_middleware_sends_503_on_http_startup_failure() -> None:
    """
    Scenario: an http request gets a 503, not a propagated exception, on failure
      Given create_tables raises
      When  an http request under the admin prefix comes through the guard
      Then  the inner app is never reached and a 503 with Retry-After is sent
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = RuntimeError("db is down")
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await middleware({"type": "http", "path": "/admin/", "root_path": ""}, None, send)

    assert len(inner.calls) == 0
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 503
    headers = dict(sent[0]["headers"])
    assert headers[b"retry-after"] == b"30"
    assert sent[1]["type"] == "http.response.body"


@pytest.mark.anyio
async def test_guard_middleware_propagates_on_websocket_startup_failure() -> None:
    """
    Scenario: a websocket connection sees the raised exception, not a 503
      Given create_tables raises
      When  a websocket scope under the admin prefix comes through the guard
      Then  the original exception propagates (there is no HTTP response to
        send on a websocket scope) and the inner app is never reached
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = RuntimeError("db is down")
    inner = _FakeASGIApp()
    middleware = StartupGuardMiddleware(inner, lifecycle=lifecycle, admin_prefix="/admin")

    with pytest.raises(RuntimeError, match="db is down"):
        await middleware(
            {"type": "websocket", "path": "/admin/realtime/ws", "root_path": ""}, None, None
        )

    assert len(inner.calls) == 0


@pytest.mark.anyio
async def test_guard_retries_are_suppressed_within_the_backoff_window() -> None:
    """
    Scenario: repeated guard failures within the backoff window run the work once
      Given create_tables always raises
      When  ensure_started() is called several times in a row (sequentially
        and concurrently) within the backoff window
      Then  create_tables is awaited only once — later calls raise
        StartupUnavailableError without re-running it
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(
        realtime_enabled=False, retry_backoff_seconds=30.0
    )
    create_tables.side_effect = RuntimeError("db is down")

    with pytest.raises(RuntimeError, match="db is down"):
        await lifecycle.ensure_started()

    with pytest.raises(StartupUnavailableError):
        await lifecycle.ensure_started()

    results = await asyncio.gather(
        *(lifecycle.ensure_started() for _ in range(5)),
        return_exceptions=True,
    )
    assert all(isinstance(r, StartupUnavailableError) for r in results)
    create_tables.assert_awaited_once()


@pytest.mark.anyio
async def test_guard_logs_full_traceback_only_for_the_first_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: only the first failure after a backoff window logs a full traceback
      Given create_tables always raises and the backoff window is 0s (so the
        very next call retries immediately instead of being suppressed)
      When  ensure_started() fails, then fails again once the window has elapsed
      Then  the first failure is logged with logger.exception (ERROR + traceback)
        and the second is logged as a plain ERROR message with no traceback —
        both attempts actually ran create_tables
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(
        realtime_enabled=False, retry_backoff_seconds=0.0
    )
    create_tables.side_effect = RuntimeError("db is down")

    with (
        caplog.at_level(logging.ERROR, logger="hyperadmin"),
        pytest.raises(RuntimeError),
    ):
        await lifecycle.ensure_started()

    with (
        caplog.at_level(logging.ERROR, logger="hyperadmin"),
        pytest.raises(RuntimeError),
    ):
        await lifecycle.ensure_started()

    tracebacks = [r for r in caplog.records if r.exc_info]
    assert len(tracebacks) == 1
    repeats = [r for r in caplog.records if "failed again" in r.getMessage()]
    assert len(repeats) == 1
    assert not repeats[0].exc_info
    assert create_tables.await_count == 2


@pytest.mark.anyio
async def test_explicit_startup_bypasses_the_backoff_window() -> None:
    """
    Scenario: the explicit startup() path never observes the backoff window
      Given a guard failure just opened the backoff window
      When  startup() (the explicit path) is called immediately after
      Then  it retries right away (raises the real error, not
        StartupUnavailableError) rather than being suppressed
    """
    lifecycle, create_tables, _sync_permissions, _drain = _make_lifecycle(realtime_enabled=False)
    create_tables.side_effect = RuntimeError("db is down")

    with pytest.raises(RuntimeError, match="db is down"):
        await lifecycle.ensure_started()

    with pytest.raises(RuntimeError, match="db is down"):
        await lifecycle.startup()

    assert create_tables.await_count == 2


# ---------------------------------------------------------------------------
# Admin lifecycle API — integration
# ---------------------------------------------------------------------------


class LifecycleWidget(SQLModel, table=True):
    __tablename__ = "lifecycle_widgets"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="")


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = dict(site._registry)
    yield
    site._registry = saved


@pytest.mark.anyio
async def test_tables_are_not_created_by_default(tmp_path) -> None:
    """
    Scenario: tables are not created by default
      Given Admin with a host engine and default settings
      When  the app starts (admin.startup() runs)
      Then  no CREATE TABLE statement is executed
    """
    # Given
    db_path = tmp_path / "host.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings())
    admin.mount("/admin")

    # When
    await admin.startup()

    # Then
    assert "lifecycle_widgets" not in await _table_names(engine)


@pytest.mark.anyio
async def test_demo_mode_still_works_zero_config(tmp_path) -> None:
    """
    Scenario: demo mode still works zero-config
      Given Admin(app) is built with no engine and no session factory
      When  a client requests GET /admin/
      Then  the response status is 200
    """
    # Given
    db_path = tmp_path / "demo.db"
    app = FastAPI()
    admin = Admin(app, settings=HyperAdminSettings(database_url=f"sqlite+aiosqlite:///{db_path}"))
    admin.mount("/admin")

    # When
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/")

    # Then
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_permission_sync_runs_under_a_host_lifespan(tmp_path) -> None:
    """
    Scenario: permission sync runs under a host lifespan
      Given a host app with its OWN lifespan= (which does not compose
        admin.lifespan()) and built-in auth
      When  two requests hit /admin/login
      Then  the permission sync runs exactly once (not on every request, and
        not skipped because a host lifespan was present) and the permission
        table contains rows for the registered model — both synced by the
        first-request safety net, not the host's lifespan
    """

    # Given
    @asynccontextmanager
    async def host_lifespan(_app: FastAPI):
        yield

    db_path = tmp_path / "authz.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # A host lifespan IS composed here — admin.lifespan() is not part of it —
    # so the guard, not the host's lifespan, must be what runs the sync.
    app = FastAPI(lifespan=host_lifespan)
    site.register(LifecycleWidget, admin_class=type("WidgetAdmin", (ModelAdmin,), {}))
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="x" * 40),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )
    admin.mount("/admin")

    real_sync_permissions = admin._sync_permissions
    sync_mock = AsyncMock(side_effect=real_sync_permissions)
    admin._lifecycle._sync_permissions = sync_mock

    # When
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/admin/login")
        await client.get("/admin/login")

    # Then
    assert sync_mock.await_count == 1
    async with engine.connect() as conn:
        result = await conn.execute(
            select(Permission.codename).where(Permission.codename == "view_lifecyclewidget")
        )
        assert result.scalar_one_or_none() == "view_lifecyclewidget"


@pytest.mark.anyio
async def test_create_tables_hyperadmin_scope_creates_only_hyperadmin_tables(
    tmp_path,
) -> None:
    """
    Scenario: admin.create_tables(scope="hyperadmin") creates only hyperadmin tables
      Given an empty database and a host model registered on SQLModel.metadata
      When  admin.create_tables(scope="hyperadmin") runs
      Then  only hyperadmin_* tables exist — the host's own table does not
    """
    # Given
    db_path = tmp_path / "scoped.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings())

    # When
    await admin.create_tables(scope="hyperadmin")

    # Then
    names = await _table_names(engine)
    assert "hyperadmin_users" in names
    assert "hyperadmin_permissions" in names
    assert "lifecycle_widgets" not in names


@pytest.mark.anyio
async def test_create_tables_all_scope_creates_every_table(tmp_path) -> None:
    """
    Scenario: admin.create_tables(scope="all") creates every SQLModel table
      Given an empty database
      When  admin.create_tables(scope="all") runs
      Then  the host's own table exists too
    """
    db_path = tmp_path / "allscope.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings())

    await admin.create_tables(scope="all")

    names = await _table_names(engine)
    assert "lifecycle_widgets" in names
    assert "hyperadmin_users" in names


@pytest.mark.anyio
async def test_admin_lifespan_composes_startup_and_shutdown(tmp_path) -> None:
    """
    Scenario: admin.lifespan() can be composed into a host's own lifespan
      Given a host app whose lifespan uses "async with admin.lifespan(): yield"
      When  the app's lifespan runs
      Then  startup (table creation) completes before the body runs
    """
    db_path = tmp_path / "lifespan.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=True))
    admin.mount("/admin")

    body_ran = False
    async with admin.lifespan():
        body_ran = True
        assert "hyperadmin_permissions" in await _table_names(engine)

    assert body_ran is True
    assert admin._lifecycle.started is True


@pytest.mark.anyio
async def test_admin_shutdown_drains_realtime_connections(tmp_path) -> None:
    """
    Scenario: admin.shutdown() drains open realtime connections
      Given Admin(realtime=RealtimeSettings()) with one open connection
      When  admin.shutdown() runs
      Then  the connection is closed and the registry reports zero left
    """
    from hyperadmin.realtime import RealtimeSettings
    from hyperadmin.realtime.registry import RealtimeConnection

    db_path = tmp_path / "shutdown.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings(), realtime=RealtimeSettings())
    admin.mount("/admin")

    close = AsyncMock()
    connection = RealtimeConnection(user_id=1, transport="sse", close=close)
    await admin._realtime_registry.register(connection)

    await admin.shutdown()

    close.assert_awaited_once()
    assert admin._realtime_registry.count() == 0


@pytest.mark.anyio
async def test_explicit_private_alias_keeps_working(tmp_path) -> None:
    """
    Scenario: the kept-for-one-release private aliases still work standalone
      Given Admin with a host engine (create_tables not opted in)
      When  admin._create_db_and_tables() is called directly (as the ERP
        example does from its own host lifespan)
      Then  tables are created even though settings.create_tables is False
    """
    db_path = tmp_path / "alias.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    app = FastAPI()
    admin = Admin(app, engine=engine, settings=HyperAdminSettings(create_tables=False))

    await admin._create_db_and_tables()

    assert "hyperadmin_permissions" in await _table_names(engine)
