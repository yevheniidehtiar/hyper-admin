"""Built-in SQL spans, for engines ``opentelemetry-instrumentation-sqlalchemy`` cannot instrument.

That instrumentor refuses SQLAlchemy versions outside its supported range (2.1 at the time of
writing) and instruments a single engine per process. These listeners use only SQLAlchemy's
public cursor events and the OpenTelemetry API, and follow the instrumentor's span shape: a
``CLIENT`` span named ``"<first SQL keyword> <database>"`` with ``db.system``, ``db.name`` and
``db.statement``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from sqlalchemy import event

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_tracer = trace.get_tracer("hyperadmin_logfire.sql")
#: Attribute on SQLAlchemy's execution context that carries the open span to the after-event.
_SPAN_ATTR = "_hyperadmin_logfire_span"


def attach_sql_spans(engine: Engine) -> None:
    """Record a span for every statement ``engine`` executes."""
    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    event.listen(engine, "handle_error", _handle_error)


def span_name(statement: str, database: str | None, dialect: str) -> str:
    """``"SELECT shop"`` style name: the first keyword, then the database (spec: no SQL parsing)."""
    parts = statement.split(maxsplit=1)[:1]
    if database:
        parts.append(database)
    return " ".join(parts) or dialect


def _before_cursor_execute(
    conn: Any, _cursor: Any, statement: str, _parameters: Any, context: Any, _executemany: bool
) -> None:
    url = conn.engine.url
    dialect = conn.engine.dialect.name
    attributes = {"db.system": dialect, "db.statement": statement}
    if url.database:
        attributes["db.name"] = url.database
    span = _tracer.start_span(
        span_name(statement, url.database, dialect), kind=SpanKind.CLIENT, attributes=attributes
    )
    setattr(context, _SPAN_ATTR, span)


def _after_cursor_execute(
    _conn: Any, _cursor: Any, _statement: str, _parameters: Any, context: Any, _executemany: bool
) -> None:
    span = getattr(context, _SPAN_ATTR, None)
    if span is not None:
        span.end()


def _handle_error(exception_context: Any) -> None:
    span = getattr(exception_context.execution_context, _SPAN_ATTR, None)
    if span is None:
        return
    error = exception_context.original_exception
    span.record_exception(error)
    span.set_status(Status(StatusCode.ERROR, str(error)))
    span.end()
