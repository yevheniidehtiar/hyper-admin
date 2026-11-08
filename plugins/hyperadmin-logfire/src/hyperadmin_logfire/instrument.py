"""``instrument_admin()``: HTTP and SQL spans for an admin (SDD ``plugin-logfire.md``, phase A).

The plugin never calls ``logfire.configure()``; until the app does, logfire records nothing and
warns once (``LogfireNotConfiguredWarning``).
"""

from __future__ import annotations

import inspect
import logging
import weakref
from typing import TYPE_CHECKING, Any

import logfire
import sqlalchemy
from fastapi import FastAPI
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncEngine

from hyperadmin_logfire.plugin import PLUGIN_NAME, LogfirePlugin
from hyperadmin_logfire.sql_spans import attach_sql_spans

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from hyperadmin import Admin

logger = logging.getLogger(__name__)

#: Engines this plugin has instrumented, by either path (sync engines; weak, so tests and
#: short-lived engines are not kept alive).
_instrumented_engines: weakref.WeakSet[Engine] = weakref.WeakSet()


def instrument_admin(admin: Admin, *, http: bool = True, sql: bool = True) -> None:
    """Instrument the admin with Logfire. Idempotent; call it after ``admin.mount()``.

    HTTP spans come from FastAPI's native telemetry where it has one, else from
    ``logfire.instrument_fastapi`` on the admin's own sub-app. SQL spans come from
    ``logfire.instrument_sqlalchemy``, or from the plugin's built-in listeners where that
    instrumentor cannot instrument the engine. No-op when the plugin is disabled. Pass
    ``http=False`` or ``sql=False`` when the app already instruments FastAPI or SQLAlchemy itself.
    """
    if PLUGIN_NAME not in admin.plugins:
        return
    plugin = admin.plugins[PLUGIN_NAME]
    if not isinstance(plugin, LogfirePlugin) or plugin.instrumented:
        return
    if http and not fastapi_traces_natively():
        # The sub-app sees the admin's own routes (``/product``); the host app would only see
        # the ``/admin`` mount. In router mode the admin routes live on the host app itself.
        logfire.instrument_fastapi(admin.asgi_app or admin.app)
    if sql:
        _instrument_admin_engine(admin)
    plugin.instrumented = True


def fastapi_traces_natively() -> bool:
    """Whether FastAPI emits OpenTelemetry request spans itself (``FastAPI(telemetry=...)``).

    Such FastAPI versions trace every app once a tracer provider exists (``logfire.configure()``)
    and record the full route. ``logfire.instrument_fastapi`` would replace those spans, and it
    suppresses FastAPI's native spans for the whole process.
    """
    return "telemetry" in inspect.signature(FastAPI).parameters


def _instrument_admin_engine(admin: Admin) -> None:
    if admin.engine is None:
        logger.info(
            "hyperadmin-logfire: no admin engine (session_factory only); call "
            "logfire.instrument_sqlalchemy(engine=...) on your engine for SQL spans"
        )
        return
    instrument_engine(admin.engine)


def instrument_engine(engine: Any) -> None:
    """Give ``engine`` SQL spans exactly once, by the official instrumentor where it can."""
    sync_engine = engine.sync_engine if isinstance(engine, AsyncEngine) else engine
    if sync_engine in _instrumented_engines:
        return
    if not SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
        try:
            logfire.instrument_sqlalchemy(engine=engine)
        except RuntimeError:
            # opentelemetry-instrumentation-sqlalchemy refuses SQLAlchemy versions it does not
            # support (2.1 at the time of writing).
            logger.info(
                "hyperadmin-logfire: opentelemetry-instrumentation-sqlalchemy does not support "
                "SQLAlchemy %s; using the plugin's built-in SQL spans",
                sqlalchemy.__version__,
            )
            attach_sql_spans(sync_engine)
    elif _instrumented_engines:
        # The instrumentor instruments one engine per process and we already used it.
        attach_sql_spans(sync_engine)
    else:
        logger.info(
            "hyperadmin-logfire: SQLAlchemy is already instrumented by the app; "
            "leaving the admin engine to it"
        )
        return
    _instrumented_engines.add(sync_engine)
