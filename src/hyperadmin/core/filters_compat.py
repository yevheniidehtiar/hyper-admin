"""Adapter from legacy ``list_filter`` strings to :class:`~hyperadmin.filters.FilterDef`.

``AdminOptions.list_filter`` historically took field names; each one rendered as
an exact-match ``<select>`` driven by ``filter_<field>=<value>``. This module is
the single seam between ``core/`` and the ``filters/`` package: it wraps those
strings into :class:`LegacyFieldFilter` so the list view can treat every entry
alike, while the querystring contract (``filter_`` prefix, exact match) is
unchanged. Nothing else in ``core/`` imports ``hyperadmin.filters``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from hyperadmin.core.filtering import FILTER_PARAM_PREFIX
from hyperadmin.filters.base import FilterBinding, FilterDef, FilterRenderContext, query_value

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hyperadmin.core.filtering import FilterCondition


@dataclass(frozen=True, kw_only=True)
class LegacyFieldFilter(FilterDef):
    """Exact match on ``filter_<field>``, rendered as a single ``<select>``.

    ``ctx.choices`` supplies the options (booleans, enum members or related
    rows), exactly as ``build_filter_metadata`` provides them today.
    """

    template: ClassVar[str] = "components/filters/select.html"

    @property
    def query_keys(self) -> tuple[str, ...]:
        return (f"{FILTER_PARAM_PREFIX}{self.field}",)

    def parse(self, qs: Any) -> dict[str, Any]:
        raw = query_value(qs, self.query_keys[0])
        return {"value": raw} if raw is not None else {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        if "value" not in parsed:
            return []
        return self.typed_conditions(binding, {"": parsed["value"]})

    def describe(self, parsed: dict[str, Any]) -> str | None:
        return parsed.get("value")

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        current = base["parsed"].get("value")
        base["choices"] = [
            {**choice, "selected": str(choice["value"]) == current} for choice in ctx.choices
        ]
        return base


def collect_filters(list_filter: Iterable[FilterDef | str] | None) -> list[FilterDef]:
    """Return ``list_filter`` as filter definitions, wrapping each string.

    Raises:
        TypeError: For an entry that is neither a ``str`` nor a ``FilterDef``.
    """
    return [
        LegacyFieldFilter(field=entry) if isinstance(entry, str) else _checked(entry)
        for entry in list_filter or ()
    ]


def _checked(entry: Any) -> FilterDef:
    if not isinstance(entry, FilterDef):
        msg = f"list_filter entries must be str or FilterDef, got {type(entry).__name__}"
        raise TypeError(msg)
    return entry
