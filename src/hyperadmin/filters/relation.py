"""``MultiFKFilter``: pick several related rows for a foreign-key column."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from hyperadmin.core.filtering import MAX_IN_VALUES
from hyperadmin.filters.base import FilterBinding, FilterDef, FilterRenderContext, query_values

if TYPE_CHECKING:
    from hyperadmin.core.filtering import FilterCondition


def parse_membership(qs: Any, key: str) -> list[str]:
    """Distinct values of ``key`` (repeated or comma-separated), capped at ``MAX_IN_VALUES``."""
    seen: dict[str, None] = {}
    for raw in query_values(qs, key):
        for part in raw.split(","):
            text = part.strip()
            if text:
                seen.setdefault(text, None)
    return list(seen)[:MAX_IN_VALUES]


@dataclass(frozen=True, kw_only=True)
class MultiFKFilter(FilterDef):
    """``{field}__in`` membership over the rows of the related model.

    The sidebar shows a checklist of ``ctx.choices`` (the view prefetches them,
    like the legacy FK filter does) with the selected rows first and a search
    box that narrows the list client-side. A stale value whose row is gone just
    matches nothing.

    Args:
        searchable: Show the search box above the checklist.
    """

    template: ClassVar[str] = "components/filters/multi_relation.html"

    searchable: bool = True

    @property
    def query_keys(self) -> tuple[str, ...]:
        return (f"{self.field}__in",)

    def parse(self, qs: Any) -> dict[str, Any]:
        values = parse_membership(qs, f"{self.field}__in")
        return {"in": values} if values else {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        values = parsed.get("in")
        return self.typed_conditions(binding, {"in": values}) if values else []

    def describe(self, parsed: dict[str, Any]) -> str | None:
        values = parsed.get("in")
        return f"{len(values)} selected" if values else None

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        selected = set(base["parsed"].get("in", ()))
        choices = [
            {**choice, "selected": str(choice["value"]) in selected} for choice in ctx.choices
        ]
        choices.sort(key=lambda choice: not choice["selected"])
        base.update(choices=choices, selected_count=len(selected), more=ctx.more)
        return base
