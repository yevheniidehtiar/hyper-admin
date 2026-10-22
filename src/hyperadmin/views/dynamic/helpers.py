"""Module-level constants and helpers shared by the dynamic view mixins."""

import functools
import re
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, NamedTuple, TypeVar, cast
from urllib.parse import unquote

from fastapi import Request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.responses import StreamingResponse

from hyperadmin.core.filtering import (
    FilterCondition,
    ParsedFilters,
)
from hyperadmin.filters.base import FilterBinding, FilterDef

if TYPE_CHECKING:
    from hyperadmin.views.dynamic.core import DynamicModelView

_MAX_CHOICES_LIMIT = 200

# Caps ``?page=`` so ``(page - 1) * page_size`` stays inside a signed 64-bit
# OFFSET: a larger value overflows the DBAPI bind (SQLite raises a plain
# ``OverflowError``) instead of just returning an empty page.
_MAX_LIST_PAGE = 10**15

# URL filter operators list_view accepts. Range operators (gte/lte/in/isnull)
# are deferred to a follow-up milestone (BYOA SDD Owner decision 8); widening
# this set is the only change list_view needs to accept them.
_LIST_FILTER_OPS = frozenset({"exact"})

#: ``id`` of the ``<tbody>`` in ``components/table_body.html``: the element a
#: filter-sidebar request targets, so ``HX-Target`` names it (filter library SDD).
LIST_BODY_ID = "model-list-body"
#: ``id`` of the whole table wrapper that search, sort and pagination target.
_LIST_TABLE_ID = "model-list"


class _ListFilters(NamedTuple):
    """What ``list_view`` derives from the querystring before it queries."""

    parsed: ParsedFilters
    explicit: list[FilterDef]
    binding: FilterBinding | None
    conditions: list[FilterCondition]
    #: The querystring to push when a ``CurrentPeriodDefault`` applies, else ``None``.
    pushed_query: str | None


# Missing-table messages from SQLite ("no such table"), PostgreSQL
# ('relation "x" does not exist') and asyncpg ("UndefinedTableError").
_MISSING_TABLE_RE = re.compile(
    r'no such table|relation "[^"]+" does not exist|UndefinedTable', re.IGNORECASE
)


def _is_missing_table_error(exc: SQLAlchemyError) -> bool:
    """Whether ``exc`` means the model's table has not been created yet."""
    return bool(_MISSING_TABLE_RE.search(str(exc)))


_HandlerT = TypeVar("_HandlerT", bound=Callable[..., Awaitable[Any]])


def _request_scoped(handler: _HandlerT) -> _HandlerT:
    """Run a ``DynamicModelView`` handler inside its request's queryset scope.

    Every adapter call the handler makes (``get``, ``list``, ``update``,
    ``get_choices``, ...) therefore applies the registered ``get_queryset`` row
    filters of the request being served, and never another request's.
    """

    @functools.wraps(handler)
    async def wrapper(self: "DynamicModelView", request: Request, *args: Any, **kwargs: Any) -> Any:
        with self._request_queryset_filter(request):
            return await handler(self, request, *args, **kwargs)

    return cast("_HandlerT", wrapper)


def _integrity_error_to_field_errors(exc: IntegrityError) -> dict[str, str]:
    """Parse an IntegrityError into {field_name: message} for form display."""
    msg = str(exc.orig) if exc.orig else str(exc)
    # SQLite: "UNIQUE constraint failed: users.username"  # noqa: ERA001
    match = re.search(r"UNIQUE constraint failed:\s*\S+\.(\w+)", msg)
    if match:
        field = match.group(1)
        return {field: f"{field.replace('_', ' ').title()} already exists."}
    # PostgreSQL: 'duplicate key ... unique constraint "users_username_key"'  # noqa: ERA001
    match = re.search(r'duplicate key value violates unique constraint "(\w+)"', msg)
    if match:
        constraint = match.group(1)
        # Try to extract field name from constraint name (e.g. "users_username_key" → "username")
        parts = constraint.rsplit("_key", 1)[0].split("_", 1)
        field = parts[1] if len(parts) > 1 else parts[0]
        return {field: f"{field.replace('_', ' ').title()} already exists."}
    return {"__all__": "A record with these values already exists."}


# --- Panel response helpers (docs/specs/detail-panels.md) -------------------

_DISPOSITION_EXT_FILENAME_RE = re.compile(r"filename\*\s*=\s*(?:utf-8|UTF-8)''([^;]+)")
_DISPOSITION_FILENAME_RE = re.compile(r'filename\s*=\s*"?([^";]+)"?')
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")
_SIZE_STEP = 1024


async def _discard_stream(response: StreamingResponse) -> None:
    """Close a streaming body that will never be sent.

    ``render_panel_view`` only inspects the response's type and headers; the
    body generator is finalised here so a handler that opens a resource at the
    top of its generator never leaks it.
    """
    aclose = getattr(response.body_iterator, "aclose", None)
    if aclose is not None:
        await aclose()


def _disposition_filename(value: str | None) -> str | None:
    """Return the file name a ``Content-Disposition`` header carries, if any."""
    if not value:
        return None
    match = _DISPOSITION_EXT_FILENAME_RE.search(value)
    if match:
        return unquote(match.group(1).strip())
    match = _DISPOSITION_FILENAME_RE.search(value)
    return match.group(1).strip() if match else None


def _human_size(value: str | None) -> str | None:
    """Format a ``Content-Length`` value as ``"182 KB"``; ``None`` when absent or invalid."""
    if value is None or not value.isdigit():
        return None
    size = float(value)
    unit = _SIZE_UNITS[0]
    for unit in _SIZE_UNITS:
        if size < _SIZE_STEP or unit == _SIZE_UNITS[-1]:
            break
        size /= _SIZE_STEP
    return f"{int(size)} {unit}" if unit == _SIZE_UNITS[0] else f"{size:.0f} {unit}"


def _as_attachment(disposition: str) -> str:
    """Turn an ``inline`` (or missing) disposition into ``attachment``, keeping its parameters."""
    kind, sep, params = disposition.partition(";")
    if kind.strip().lower() == "attachment":
        return disposition
    return f"attachment{sep}{params}" if sep else "attachment"
