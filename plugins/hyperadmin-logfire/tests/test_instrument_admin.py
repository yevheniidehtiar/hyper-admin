"""Unit tests for ``instrument_admin()`` (``docs/specs/plugin-logfire.md``, phase A scenarios)."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import anyio
import logfire
import pytest
import sqlalchemy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from logfire.testing import TestExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import StatusCode
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_logfire import instrument, instrument_admin, sql_spans

#: Instrumentation scope of the plugin's built-in SQL spans.
BUILT_IN_SQL_SCOPE = "hyperadmin_logfire.sql"


class TracedOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    number: str = "ORD-1"


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry() -> Iterator[None]:
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture(autouse=True)
def reset_sql_instrumentation() -> Iterator[None]:
    """The SQLAlchemy instrumentor is a process-wide singleton (a second instrument() is a
    silent no-op), and the plugin remembers the engines it instrumented: reset both."""
    yield
    instrumentor = SQLAlchemyInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    instrument._instrumented_engines.clear()


@pytest.fixture
def exporter() -> TestExporter:
    """Configure logfire to record spans in memory (not sent anywhere)."""
    span_exporter = TestExporter()
    logfire.configure(
        send_to_logfire=False,
        console=False,
        additional_span_processors=[SimpleSpanProcessor(span_exporter)],
    )
    return span_exporter


@pytest.fixture
def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(eng) as session:
            session.add(TracedOrder(id=1, number="ORD-1001"))
            await session.commit()

    anyio.run(setup)
    return eng


def _admin(engine: AsyncEngine | None, **admin_kwargs: Any) -> Admin:
    settings = admin_kwargs.pop("settings", HyperAdminSettings(create_tables=False))
    admin = Admin(app=FastAPI(), engine=engine, settings=settings, **admin_kwargs)
    site.register(TracedOrder, _Admin)
    admin.mount(path="/admin")
    return admin


def _list_orders(admin: Admin) -> None:
    response = TestClient(admin.app).get("/admin/tracedorder")
    assert response.status_code == 200


def _spans(exporter: TestExporter) -> list[dict[str, Any]]:
    return exporter.exported_spans_as_dict()


def _http_spans(exporter: TestExporter) -> list[dict[str, Any]]:
    return [s for s in _spans(exporter) if "http.route" in s["attributes"]]


def _sql_spans(exporter: TestExporter) -> list[dict[str, Any]]:
    return [s for s in _spans(exporter) if "db.statement" in s["attributes"]]


def _built_in_sql_spans(exporter: TestExporter) -> list[ReadableSpan]:
    return [
        s
        for s in exporter.exported_spans
        if s.instrumentation_scope is not None
        and s.instrumentation_scope.name == BUILT_IN_SQL_SCOPE
        # logfire also exports a "pending" copy of each span when it starts
        and (s.attributes or {}).get("logfire.span_type") != "pending_span"
    ]


def _record_calls(monkeypatch: pytest.MonkeyPatch, name: str) -> list[Any]:
    calls: list[Any] = []
    monkeypatch.setattr(logfire, name, lambda *args, **kwargs: calls.append((args, kwargs)))
    return calls


def _fastapi_native(monkeypatch: pytest.MonkeyPatch, native: bool) -> None:
    monkeypatch.setattr(instrument, "fastapi_traces_natively", lambda: native)


def _refuse_sqlalchemy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the official instrumentor refuse the installed SQLAlchemy, as it does on 2.1."""

    def unsupported(**_: Any) -> None:
        raise RuntimeError("could not instrument SQLAlchemy")

    monkeypatch.setattr(logfire, "instrument_sqlalchemy", unsupported)


def _run(engine: AsyncEngine, sql: str) -> None:
    async def go() -> None:
        async with engine.connect() as conn:
            await conn.execute(text(sql))

    anyio.run(go)


# -- HTTP -----------------------------------------------------------------------------------


def test_instrument_admin_emits_http_and_sql_spans(
    exporter: TestExporter, engine: AsyncEngine
) -> None:
    """
    Scenario: instrument_admin emits HTTP and SQL spans
      Given logfire is configured with a test exporter
      And   instrument_admin(admin) has been called
      When  GET /admin/tracedorder is requested
      Then  the exporter holds one HTTP server span for the request
      And   at least one SQL span is in the same trace

    Runs on whichever path the installed FastAPI takes: native telemetry on FastAPI 0.143+,
    ``logfire.instrument_fastapi`` on the admin sub-app on older FastAPI (the lowest-direct
    CI job). Not parametrized: ``instrument_fastapi`` suppresses FastAPI's native spans
    process-wide, which would leak into every later test.
    """
    admin = _admin(engine)
    instrument_admin(admin)

    _list_orders(admin)

    (http_span,) = _http_spans(exporter)
    # Native telemetry records the full route; the sub-app instrumentor its own route.
    route = "/admin/tracedorder" if instrument.fastapi_traces_natively() else "/tracedorder"
    assert http_span["attributes"]["http.route"] == route
    sql_traces = {s["context"]["trace_id"] for s in _sql_spans(exporter)}
    assert http_span["context"]["trace_id"] in sql_traces


class _PlainBase(DeclarativeBase):
    pass


class PlainInvoice(_PlainBase):
    """A plain SQLAlchemy model (no SQLModel), served by ``SQLAlchemyAdapter``."""

    __tablename__ = "plain_invoice"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(default="INV-1")


class _PlainAdmin(ModelAdmin):
    adapter_class = SQLAlchemyAdapter


def test_instrument_admin_traces_a_plain_sqlalchemy_model(exporter: TestExporter) -> None:
    """
    Scenario: an admin over plain SQLAlchemy models
      Given a DeclarativeBase model registered with SQLAlchemyAdapter
      And   instrument_admin(admin) has been called
      When  GET /admin/plaininvoice is requested
      Then  the request's HTTP span and its SQL spans share one trace
    """
    plain_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with plain_engine.begin() as conn:
            await conn.run_sync(_PlainBase.metadata.create_all)
            await conn.execute(text("INSERT INTO plain_invoice (id, number) VALUES (1, 'INV-7')"))

    anyio.run(setup)
    admin = Admin(
        app=FastAPI(), engine=plain_engine, settings=HyperAdminSettings(create_tables=False)
    )
    site.register(PlainInvoice, _PlainAdmin)
    admin.mount(path="/admin")
    instrument_admin(admin)

    response = TestClient(admin.app).get("/admin/plaininvoice")

    assert response.status_code == 200
    assert "INV-7" in response.text
    (http_span,) = _http_spans(exporter)
    plain_sql = [
        s for s in _sql_spans(exporter) if "plain_invoice" in s["attributes"]["db.statement"]
    ]
    assert plain_sql
    assert {s["context"]["trace_id"] for s in plain_sql} == {http_span["context"]["trace_id"]}


def test_native_fastapi_telemetry_is_detected() -> None:
    """
    Scenario: the installed FastAPI traces requests itself
      Given FastAPI accepts the telemetry= option
      When  fastapi_traces_natively() is called
      Then  it reports native tracing, so instrument_admin leaves HTTP spans to FastAPI
    """
    assert instrument.fastapi_traces_natively() is (
        "telemetry" in inspect.signature(FastAPI).parameters
    )


def test_instrument_admin_instruments_the_admin_sub_app_on_older_fastapi(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: FastAPI without native telemetry
      Given an admin mounted in the default isolated mode
      And   FastAPI has no native telemetry
      When  instrument_admin(admin) is called
      Then  logfire.instrument_fastapi instruments the admin sub-app, not the host app
    """
    _fastapi_native(monkeypatch, False)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")
    admin = _admin(engine)

    instrument_admin(admin, sql=False)

    assert admin.asgi_app is not None
    assert http_calls == [((admin.asgi_app,), {})]


def test_instrument_admin_instruments_the_host_app_in_router_mode(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: legacy router mode on FastAPI without native telemetry
      Given an admin mounted with mount_mode="router" (admin routes on the host app)
      When  instrument_admin(admin) is called
      Then  logfire.instrument_fastapi instruments the host app
    """
    _fastapi_native(monkeypatch, False)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")
    with pytest.warns(DeprecationWarning, match="router"):
        admin = _admin(
            engine, settings=HyperAdminSettings(create_tables=False, mount_mode="router")
        )

    instrument_admin(admin, sql=False)

    assert admin.asgi_app is None
    assert http_calls == [((admin.app,), {})]


def test_instrument_admin_leaves_native_fastapi_telemetry_alone(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: FastAPI with native telemetry
      Given FastAPI traces requests itself
      When  instrument_admin(admin) is called
      Then  logfire.instrument_fastapi is not called (it would suppress the native spans)
    """
    _fastapi_native(monkeypatch, True)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")

    instrument_admin(_admin(engine), sql=False)

    assert http_calls == []


# -- SQL ------------------------------------------------------------------------------------


def test_instrument_admin_falls_back_to_built_in_sql_spans_on_unsupported_sqlalchemy(
    exporter: TestExporter,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: SQLAlchemy the official instrumentor refuses (2.1)
      Given logfire.instrument_sqlalchemy raises RuntimeError for the installed SQLAlchemy
      When  instrument_admin(admin) is called and GET /admin/tracedorder is requested
      Then  no exception is raised
      And   an INFO log record names the SQLAlchemy version
      And   the built-in SQL spans are in the request's trace, shaped like the instrumentor's
    """
    _refuse_sqlalchemy(monkeypatch)
    admin = _admin(engine)

    with caplog.at_level(logging.INFO, logger="hyperadmin_logfire"):
        instrument_admin(admin)
    _list_orders(admin)

    assert any(sqlalchemy.__version__ in r.getMessage() for r in caplog.records)
    (http_span,) = _http_spans(exporter)
    built_in = _built_in_sql_spans(exporter)
    assert built_in
    select = next(s for s in built_in if s.name.startswith("SELECT"))
    assert select.name == "SELECT :memory:"
    assert select.kind.name == "CLIENT"
    assert select.attributes is not None
    assert select.attributes["db.system"] == "sqlite"
    assert select.attributes["db.name"] == ":memory:"
    assert "tracedorder" in str(select.attributes["db.statement"])
    assert select.context.trace_id == http_span["context"]["trace_id"]


def test_built_in_sql_span_records_a_failed_statement(
    exporter: TestExporter, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: a statement fails on an engine with built-in SQL spans
      Given the built-in SQL spans are attached to an engine
      When  a statement against a missing table is executed
      Then  the span ends with status ERROR and records the exception
    """
    _refuse_sqlalchemy(monkeypatch)
    instrument.instrument_engine(engine)

    with pytest.raises(OperationalError):
        _run(engine, "SELECT * FROM missing_table")

    (span,) = [
        s for s in _built_in_sql_spans(exporter) if "missing_table" in s.name + str(s.attributes)
    ]
    assert span.status.status_code is StatusCode.ERROR
    assert [e.name for e in span.events] == ["exception"]


def test_a_second_admin_engine_gets_built_in_sql_spans(
    exporter: TestExporter, engine: AsyncEngine
) -> None:
    """
    Scenario: two admin engines in one process
      Given a first engine has been instrumented
      When  instrument_engine is called for a second engine
      Then  the second engine's statements get built-in SQL spans
      And   the first engine's statements still get exactly one SQL span each

    The first engine's spans are the official instrumentor's on SQLAlchemy 2.0 and the
    built-in ones on 2.1 (which the instrumentor refuses); either way each statement has one.
    """
    second = create_engine("sqlite://")

    instrument.instrument_engine(engine)
    instrument.instrument_engine(second)
    with second.connect() as conn:
        conn.execute(text("SELECT 2"))
    _run(engine, "SELECT 1")

    built_in = [s.attributes["db.statement"] for s in _built_in_sql_spans(exporter) if s.attributes]
    assert "SELECT 2" in built_in
    statements = [
        s["attributes"]["db.statement"]
        for s in _sql_spans(exporter)
        if s["attributes"].get("logfire.span_type") != "pending_span"
    ]
    assert statements.count("SELECT 1") == 1
    assert statements.count("SELECT 2") == 1


def test_instrument_engine_is_idempotent_per_engine(
    exporter: TestExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: the same engine is instrumented twice
      Given an engine with built-in SQL spans
      When  instrument_engine is called for it again
      Then  each statement still gets exactly one span
    """
    _refuse_sqlalchemy(monkeypatch)
    sync_engine = create_engine("sqlite://")

    instrument.instrument_engine(sync_engine)
    instrument.instrument_engine(sync_engine)
    with sync_engine.connect() as conn:
        conn.execute(text("SELECT 3"))

    assert len(_built_in_sql_spans(exporter)) == 1


def test_instrument_admin_leaves_an_app_instrumented_sqlalchemy_alone(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: the app instrumented SQLAlchemy itself
      Given SQLAlchemyInstrumentor().instrument() ran before the admin
      When  instrument_admin(admin) is called
      Then  the plugin neither re-instruments nor adds built-in spans
      And   an INFO log record says the engine is left to the app

    skip_dep_check: on SQLAlchemy 2.1 the app's own instrument() would be refused, and the
    plugin then (correctly) instruments the engine itself; here the app's call succeeded.
    """
    SQLAlchemyInstrumentor().instrument(skip_dep_check=True)
    attached: list[Any] = []
    monkeypatch.setattr(instrument, "attach_sql_spans", attached.append)
    sql_calls = _record_calls(monkeypatch, "instrument_sqlalchemy")

    with caplog.at_level(logging.INFO, logger="hyperadmin_logfire"):
        instrument_admin(_admin(engine), http=False)

    assert sql_calls == []
    assert attached == []
    assert any("already instrumented" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    ("statement", "database", "expected"),
    [
        ("SELECT 1", "shop", "SELECT shop"),
        ("  insert into t values (1)", None, "insert"),
        ("", None, "sqlite"),
    ],
)
def test_built_in_span_name_follows_the_instrumentor(
    statement: str, database: str | None, expected: str
) -> None:
    """
    Scenario: built-in SQL span names
      Given a statement and the engine's database
      When  the span name is built
      Then  it is the first keyword and the database, or the dialect when both are empty
    """
    assert sql_spans.span_name(statement, database, "sqlite") == expected


def test_built_in_error_hook_ignores_executions_without_a_span() -> None:
    """
    Scenario: an error before any statement ran (e.g. while connecting)
      Given an exception context with no execution context
      When  the built-in error hook runs
      Then  it does nothing
    """
    sql_spans._handle_error(SimpleNamespace(execution_context=None))


# -- Plugin state and opt-outs --------------------------------------------------------------


def test_instrument_admin_instruments_nothing_when_the_plugin_is_disabled(
    exporter: TestExporter, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: instrument_admin is a no-op when the plugin is disabled
      Given hyperadmin-logfire is installed
      And   Admin is constructed with disabled_plugins=["logfire"]
      When  instrument_admin(admin) is called and GET /admin/tracedorder is requested
      Then  neither FastAPI nor SQLAlchemy is instrumented
      And   the exporter holds no SQL spans
    """
    _fastapi_native(monkeypatch, False)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")
    admin = _admin(engine, disabled_plugins=["logfire"])

    instrument_admin(admin)
    _list_orders(admin)

    assert http_calls == []
    assert not _sql_spans(exporter)


def test_instrument_admin_ignores_a_foreign_plugin_named_logfire(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: another plugin registered under the name "logfire"
      Given hyperadmin-logfire is disabled
      And   a different plugin class is registered as "logfire"
      When  instrument_admin(admin) is called
      Then  nothing is instrumented
    """

    class ForeignPlugin:
        name = "logfire"

        def on_register(self, admin: Any) -> None:
            """Contribute nothing."""

    sql_calls = _record_calls(monkeypatch, "instrument_sqlalchemy")
    admin = _admin(engine, disabled_plugins=["logfire"])
    assert admin.plugins.register(ForeignPlugin(), admin=admin)

    instrument_admin(admin)

    assert sql_calls == []


def test_instrument_admin_twice_instruments_once(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: a second instrument_admin call is a no-op
      Given FastAPI has no native telemetry
      And   instrument_admin(admin) has been called
      When  instrument_admin(admin) is called again
      Then  FastAPI and SQLAlchemy were each instrumented once
    """
    _fastapi_native(monkeypatch, False)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")
    sql_calls = _record_calls(monkeypatch, "instrument_sqlalchemy")
    admin = _admin(engine)

    instrument_admin(admin)
    instrument_admin(admin)

    assert http_calls == [((admin.asgi_app,), {})]
    assert sql_calls == [((), {"engine": engine})]


def test_instrument_admin_honours_the_http_and_sql_opt_outs(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: the app already instruments FastAPI and SQLAlchemy itself
      Given an admin with an engine on a FastAPI without native telemetry
      When  instrument_admin(admin, http=False, sql=False) is called
      Then  neither FastAPI nor SQLAlchemy is instrumented by the plugin
    """
    _fastapi_native(monkeypatch, False)
    http_calls = _record_calls(monkeypatch, "instrument_fastapi")
    sql_calls = _record_calls(monkeypatch, "instrument_sqlalchemy")

    instrument_admin(_admin(engine), http=False, sql=False)

    assert http_calls == []
    assert sql_calls == []


def test_instrument_admin_without_an_engine_explains_how_to_get_sql_spans(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: an admin built from a session factory has no engine to instrument
      Given an admin whose engine is None
      When  instrument_admin(admin) is called
      Then  SQLAlchemy is not instrumented
      And   an INFO log record tells the user to instrument their own engine
    """
    sql_calls = _record_calls(monkeypatch, "instrument_sqlalchemy")
    admin = _admin(engine)
    admin.engine = None

    with caplog.at_level(logging.INFO, logger="hyperadmin_logfire"):
        instrument_admin(admin, http=False)

    assert sql_calls == []
    assert any("instrument_sqlalchemy" in r.getMessage() for r in caplog.records)
