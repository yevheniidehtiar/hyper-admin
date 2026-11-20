"""The report page's filter sidebar: the list view's filter groups, driving a report.

:func:`build_filter_panel` renders one sidebar group per declared filter with
the filter library's own partials, so a report's filters look and behave like a
list view's (presets, inline errors, "Clear" links, applied-filter chips).

Filters that pick from a list (a plain field name, ``MultiFKFilter``, a
``MultiChoiceFilter`` without declared choices) offer the values *present in
the report's source*: a boolean is Yes/No, an enum lists its members, anything
else is the first :data:`CHOICE_LIMIT` distinct values of the column. A foreign
key shows the related rows' display names, as a ``Many2One`` aggregate does.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, get_args
from urllib.parse import urlencode

from markupsafe import Markup
from sqlalchemy import select

from hyperadmin.core.display import get_enum_label
from hyperadmin.core.filters_compat import LegacyFieldFilter
from hyperadmin.core.schema import schema_for
from hyperadmin.filters import FilterRenderContext, MultiChoiceFilter, MultiFKFilter
from hyperadmin.filters.base import clear_href, query_pairs, query_values
from hyperadmin_reports.filtering import bind, filter_defs
from hyperadmin_reports.view import display_names, fk_target

if TYPE_CHECKING:
    from jinja2 import Environment
    from sqlalchemy.ext.asyncio import AsyncSession

    from hyperadmin.filters import FilterBinding, FilterDef
    from hyperadmin_reports.view import ReportView

#: Most distinct source values a filter checklist offers (applied values always show).
CHOICE_LIMIT = 50

_BOOL_CHOICES = ({"value": "true", "label": "Yes"}, {"value": "false", "label": "No"})


def needs_choices(filter_def: FilterDef) -> bool:
    """Whether the sidebar needs prefetched options to render ``filter_def``."""
    if isinstance(filter_def, (LegacyFieldFilter, MultiFKFilter)):
        return True
    return isinstance(filter_def, MultiChoiceFilter) and filter_def.choices is None


def _annotation(model: type[Any], field: str) -> Any:
    """The declared type of ``model.field`` with ``Optional`` removed, or ``None``."""
    try:
        info = schema_for(model).model_fields.get(field)
    except TypeError:  # a mapped class the schema registry has no builder for
        return None
    annotation = getattr(info, "annotation", None)
    inner = [arg for arg in get_args(annotation) if arg is not type(None)]
    return inner[0] if len(inner) == 1 else annotation


async def _source_choices(
    report: type[ReportView], session: AsyncSession, field: str, applied: list[str]
) -> list[dict[str, Any]]:
    """Distinct values of ``field`` in the report's source, applied values included."""
    column = getattr(report.source_model(), field)
    query = (
        select(column).where(column.is_not(None)).distinct().order_by(column).limit(CHOICE_LIMIT)
    )
    values = list((await session.execute(query)).scalars())
    target = fk_target(report.model, field)
    names = await display_names(session, target, set(values)) if target and values else {}
    choices = [{"value": str(value), "label": str(names.get(value, value))} for value in values]
    listed = {choice["value"] for choice in choices}
    choices.extend({"value": raw, "label": raw} for raw in applied if raw not in listed)
    return choices


async def filter_choices(
    report: type[ReportView], session: AsyncSession, query: Any
) -> dict[str, list[dict[str, Any]]]:
    """Options keyed by field, for the filters that pick from a list."""
    choices: dict[str, list[dict[str, Any]]] = {}
    for filter_def in filter_defs(report):
        name = filter_def.field
        if name in choices or not needs_choices(filter_def):
            continue
        annotation = _annotation(report.model, name)
        if annotation is bool:
            choices[name] = [dict(choice) for choice in _BOOL_CHOICES]
        elif isinstance(annotation, type) and issubclass(annotation, Enum):
            choices[name] = [
                {"value": str(member.value), "label": get_enum_label(member)}
                for member in annotation
            ]
        else:
            applied = [v for key in filter_def.query_keys for v in query_values(query, key)]
            applied = [part.strip() for raw in applied for part in raw.split(",") if part.strip()]
            choices[name] = await _source_choices(report, session, name, applied)
    return choices


async def build_filter_panel(
    report: type[ReportView],
    session: AsyncSession,
    query: Any,
    *,
    binding: FilterBinding | None = None,
    templates: Environment | None = None,
) -> dict[str, Any] | None:
    """Context of the report page's filter sidebar, or ``None`` without filters.

    ``groups`` holds one rendered sidebar group per filter, ``applied`` the
    chips of the active ones, ``kept`` the querystring pairs that are not a
    filter's (the period override) and so survive "Apply" and "Reset", and
    ``reset_query`` the ``?...`` suffix that clears every filter.
    """
    defs = filter_defs(report)
    if not defs:
        return None
    bound = bind(report, binding)
    choices = await filter_choices(report, session, query)
    groups: list[dict[str, Any]] = []
    for filter_def in defs:
        parsed = filter_def.parse(query)
        ctx = FilterRenderContext(
            query=query,
            binding=bound,
            choices=choices.get(filter_def.field, ()),  # type: ignore[arg-type]
            templates=templates,
        )
        groups.append(
            {
                "slug": filter_def.slug,
                "title": filter_def.title,
                # Rendered by an autoescaping Jinja environment (the admin's, or the package's).
                "html": Markup(filter_def.render(ctx)),  # noqa: S704
                "chip": filter_def.describe(parsed),
                "error": filter_def.error(query),
                "clear_href": clear_href(query, filter_def.query_keys),
            }
        )
    keys = {key for filter_def in defs for key in filter_def.query_keys} | {"embed", "page"}
    kept = [(key, value) for key, value in query_pairs(query) if key not in keys]
    return {
        "groups": groups,
        "applied": [
            {"label": g["title"], "value": g["chip"], "clear_href": g["clear_href"]}
            for g in groups
            if g["chip"]
        ],
        "kept": kept,
        "reset_query": f"?{urlencode(kept)}" if kept else "",
    }
