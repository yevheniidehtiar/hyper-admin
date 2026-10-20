"""``MultiChoiceFilter``: pick several values of an enum or a fixed choice list."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from hyperadmin.core.display import get_enum_label
from hyperadmin.filters.base import FilterBinding, FilterDef, FilterRenderContext
from hyperadmin.filters.relation import parse_membership

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hyperadmin.core.filtering import FilterCondition


@dataclass(frozen=True, kw_only=True)
class MultiChoiceFilter(FilterDef):
    """``{field}__in`` membership over a known set of values.

    Args:
        choices: An ``Enum`` class, or ``(value, label)`` pairs. When given,
            unknown querystring values are dropped; when ``None``, the view
            supplies ``ctx.choices`` and any value is passed to the typed pipeline.
    """

    template: ClassVar[str] = "components/filters/multi_choice.html"

    choices: type[Enum] | Sequence[tuple[str, str]] | None = None

    @property
    def query_keys(self) -> tuple[str, ...]:
        return (f"{self.field}__in",)

    @property
    def options(self) -> list[tuple[str, str]]:
        """The declared choices as ``(value, label)`` pairs (``[]`` when undeclared)."""
        if self.choices is None:
            return []
        if isinstance(self.choices, type) and issubclass(self.choices, Enum):
            return [(str(member.value), get_enum_label(member)) for member in self.choices]
        return [(str(value), str(label)) for value, label in self.choices]

    def parse(self, qs: Any) -> dict[str, Any]:
        values = parse_membership(qs, f"{self.field}__in")
        if self.choices is not None:
            known = {value for value, _label in self.options}
            values = [value for value in values if value in known]
        return {"in": values} if values else {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        values = parsed.get("in")
        return self.typed_conditions(binding, {"in": values}) if values else []

    def describe(self, parsed: dict[str, Any]) -> str | None:
        values: list[str] = parsed.get("in") or []
        if not values:
            return None
        labels = dict(self.options)
        return ", ".join(labels.get(value, value) for value in values)

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        selected = set(base["parsed"].get("in", ()))
        options = self.options or [(str(c["value"]), str(c["label"])) for c in ctx.choices]
        base["choices"] = [
            {"value": value, "label": label, "selected": value in selected}
            for value, label in options
        ]
        return base
