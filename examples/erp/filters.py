"""ERP list filters shared by the sales and purchases admins."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, ClassVar

from hyperadmin.core.filtering import FilterCondition
from hyperadmin.filters import FilterBinding, FilterDef
from hyperadmin.filters.base import is_truthy, query_value


@dataclass(frozen=True, kw_only=True)
class OverdueFilter(FilterDef):
    """The "Overdue only" switch: ``open_status`` rows whose due date is before today.

    Matches the "Overdue" status pill, so what the clerk filters is what the pill says.
    """

    template: ClassVar[str] = "filters/overdue.html"

    open_status: Any
    label: str | None = "Overdue only"
    help_text: str = "Unpaid, with a due date before today."

    @property
    def slug(self) -> str:
        return "overdue"

    @property
    def query_keys(self) -> tuple[str, ...]:
        return ("overdue",)

    def parse(self, qs: Any) -> dict[str, Any]:
        return {"overdue": True} if is_truthy(query_value(qs, "overdue")) else {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        if not parsed.get("overdue"):
            return []
        today = (binding or FilterBinding()).today_date
        return [
            FilterCondition("status", "exact", self.open_status),
            FilterCondition(self.field, "lte", today - timedelta(days=1)),
        ]

    def describe(self, parsed: dict[str, Any]) -> str | None:
        return self.title if parsed.get("overdue") else None
