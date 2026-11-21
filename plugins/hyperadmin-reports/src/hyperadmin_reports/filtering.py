"""Report filters: the core filter library applied to a report's source.

A report declares ``filters`` exactly like ``AdminOptions.list_filter``: field
names (the legacy ``filter_<field>`` select) or
:class:`~hyperadmin.filters.FilterDef` instances. The pipeline is the list
view's own: each filter parses the querystring, compiles to typed
:class:`~hyperadmin.core.filtering.FilterCondition` objects, and the adapters'
shared clause builder turns those into SQLAlchemy clauses. Here the clauses are
built against :meth:`ReportView.source_model` (the cache's fact table when
``cache`` is set) and go through the ``where`` seam, so they narrow the rows
*before* any aggregate sees them.

The model's annotations type the values (the fact table's when the model does
not declare the field); a value that does not coerce is dropped, never sent to
the database.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from hyperadmin.adapters.filtering import build_clauses
from hyperadmin.adapters.introspection import datetime_kind
from hyperadmin.core.filters_compat import collect_filters
from hyperadmin.filters import FilterBinding, IsOwnerFilter

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date, datetime

    from sqlalchemy.sql.elements import ColumnElement

    from hyperadmin.core.filtering import FilterCondition
    from hyperadmin.filters import FilterDef
    from hyperadmin_reports.view import ReportView

#: Querystring keys the report routes own; a filter may not read them.
RESERVED_QUERY_KEYS = frozenset({"period", "embed"})


def filter_defs(report: type[ReportView]) -> list[FilterDef]:
    """``report.filters`` as filter definitions, in order (strings become legacy selects).

    Raises:
        TypeError: For an entry that is neither a ``str`` nor a ``FilterDef``.
    """
    return collect_filters(report.filters)


def filter_fields(filter_def: FilterDef) -> tuple[str, ...]:
    """Every source column ``filter_def`` compares against."""
    if isinstance(filter_def, IsOwnerFilter):
        return tuple(filter_def.owner_fields)
    return (filter_def.field,)


def filter_query_keys(report: type[ReportView]) -> set[str]:
    """Every querystring key the report's filters read."""
    return {key for filter_def in filter_defs(report) for key in filter_def.query_keys}


def validate_filters(report: type[ReportView]) -> list[str]:
    """Check the declared filters and return the source columns they need.

    Raises:
        ValueError: For an entry that is not a field name or ``FilterDef``, or a
            filter that reads a querystring key the report routes own.
    """
    try:
        defs = filter_defs(report)
    except TypeError as exc:
        raise ValueError(f"{report.__name__}.filters: {exc}") from exc
    reserved = sorted(
        {key for filter_def in defs for key in filter_def.query_keys} & RESERVED_QUERY_KEYS
    )
    if reserved:
        raise ValueError(
            f"{report.__name__}.filters use reserved query key(s): {', '.join(reserved)}"
        )
    return [name for filter_def in defs for name in filter_fields(filter_def)]


def bind(report: type[ReportView], binding: FilterBinding | None = None) -> FilterBinding:
    """``binding`` completed with what the report knows: its model and datetime kinds.

    The caller supplies the per-request facts (timezone, today, the user); the
    model types the values and the *source* table says whether a datetime
    column is aware or naive, because that is the table the clauses run on.
    """
    source = report.source_model()
    base = binding or FilterBinding()
    return replace(
        base,
        model=base.model or report.model,
        datetime_kind=base.datetime_kind or (lambda name: datetime_kind(source, name)),
    )


def compile_filters(
    report: type[ReportView], query: Any, binding: FilterBinding | None = None
) -> list[FilterCondition]:
    """Every filter's typed conditions for ``query``, in declaration order."""
    bound = bind(report, binding)
    conditions: list[FilterCondition] = []
    for filter_def in filter_defs(report):
        conditions.extend(filter_def.compile(filter_def.parse(query), bound))
    return conditions


def filter_clauses(
    report: type[ReportView], conditions: Sequence[FilterCondition]
) -> list[ColumnElement[bool]]:
    """``conditions`` as ``WHERE`` clauses on the report's source table."""
    return build_clauses(report.source_model(), conditions)


def filtered_span(
    conditions: Sequence[FilterCondition], field: str
) -> tuple[date | datetime, date | datetime] | None:
    """The closed range the conditions put on ``field``, or ``None`` when open-ended.

    Lets ``TimeBucket(period="auto")`` size its bucket from the range the user
    asked for rather than from the rows that happen to fall inside it.
    """
    bounds = {c.op: c.value for c in conditions if c.field == field and c.op in ("gte", "lte")}
    if "gte" not in bounds or "lte" not in bounds:
        return None
    return bounds["gte"], bounds["lte"]


def filter_errors(report: type[ReportView], query: Any) -> dict[str, str]:
    """Inline messages for invalid filter input in ``query``, keyed by filter slug."""
    errors: dict[str, str] = {}
    for filter_def in filter_defs(report):
        message = filter_def.error(query)
        if message is not None:
            errors[filter_def.slug] = message
    return errors


def describe_filters(report: type[ReportView], query: Any) -> dict[str, str]:
    """The applied filters as ``{title: chip text}``, in declaration order.

    Feeds the page's applied-filter chips and the XLSX "Filters used" sheet.
    """
    applied: dict[str, str] = {}
    for filter_def in filter_defs(report):
        text = filter_def.describe(filter_def.parse(query))
        if text is not None:
            applied[filter_def.title] = text
    return applied
