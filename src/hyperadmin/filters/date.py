"""Date filters: a from/to range with presets, and a "current period" default."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from urllib.parse import urlencode

from hyperadmin.filters.base import (
    FilterBinding,
    FilterDef,
    FilterRenderContext,
    clear_href,
    query_value,
)

if TYPE_CHECKING:
    from hyperadmin.core.filtering import FilterCondition

Period = Literal["day", "week", "month", "quarter", "year"]

PERIOD_LABELS: dict[str, str] = {
    "day": "today",
    "week": "this week",
    "month": "this month",
    "quarter": "this quarter",
    "year": "this year",
}

#: Preset name -> (period, offset in periods from today, button label).
PRESETS: dict[str, tuple[Period, int, str]] = {
    "today": ("day", 0, "Today"),
    "this_week": ("week", 0, "This week"),
    "this_month": ("month", 0, "This month"),
    "last_month": ("month", -1, "Last month"),
    "this_quarter": ("quarter", 0, "This quarter"),
}
DEFAULT_PRESETS: tuple[str, ...] = tuple(PRESETS)
FROM_AFTER_TO = "“From” is after “To”. Swap the dates or pick a preset."
INVALID_DATE = "Enter a valid date (YYYY-MM-DD)."


def _month_end(day: date) -> date:
    first_next = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first_next - timedelta(days=1)


def period_bounds(period: Period, today: date, offset: int = 0) -> tuple[date, date]:
    """First and last day of the ``period`` containing ``today``, shifted by ``offset``.

    ``offset=-1`` is the previous period (last month, last week...).
    """
    if period == "day":
        day = today + timedelta(days=offset)
        return day, day
    if period == "week":
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        return start, start + timedelta(days=6)
    if period == "year":
        year = today.year + offset
        return date(year, 1, 1), date(year, 12, 31)
    months_per = 3 if period == "quarter" else 1
    index = (today.year * 12 + today.month - 1) // months_per + offset
    first_month = index * months_per
    start = date(first_month // 12, first_month % 12 + 1, 1)
    end_month = first_month + months_per - 1
    return start, _month_end(date(end_month // 12, end_month % 12 + 1, 1))


def _parse_bounds(qs: Any, field: str) -> tuple[date | None, date | None]:
    """The ``__gte``/``__lte`` dates in ``qs``; raises ``ValueError`` on a bad date."""
    gte = query_value(qs, f"{field}__gte")
    lte = query_value(qs, f"{field}__lte")
    return (
        None if gte is None else date.fromisoformat(gte),
        None if lte is None else date.fromisoformat(lte),
    )


@dataclass(frozen=True, kw_only=True)
class DateRangeFilter(FilterDef):
    """Inclusive ``from``/``to`` bounds on a date or datetime column.

    Reads ``{field}__gte``, ``{field}__lte`` and ``{field}__preset``. A valid
    preset wins over the explicit bounds (it is what the preset button
    submits). A whole day on a datetime column covers ``00:00`` to
    ``23:59:59.999999`` in the display timezone, via the typed pipeline.

    Args:
        presets: Preset buttons to show, from :data:`PRESETS`; ``()`` hides them.
    """

    template: ClassVar[str] = "components/filters/date_range.html"
    value_type: ClassVar[Any] = date

    presets: tuple[str, ...] = DEFAULT_PRESETS

    def __post_init__(self) -> None:
        unknown = sorted(set(self.presets) - set(PRESETS))
        if unknown:
            msg = f"Unknown presets {unknown}; expected a subset of {sorted(PRESETS)}"
            raise ValueError(msg)

    @property
    def query_keys(self) -> tuple[str, ...]:
        return (f"{self.field}__gte", f"{self.field}__lte", f"{self.field}__preset")

    def _preset(self, qs: Any) -> str | None:
        preset = query_value(qs, f"{self.field}__preset")
        return preset if preset in self.presets else None

    def parse(self, qs: Any) -> dict[str, Any]:
        preset = self._preset(qs)
        if preset is not None:
            return {"preset": preset}
        try:
            gte, lte = _parse_bounds(qs, self.field)
        except ValueError:
            return {}
        if gte is not None and lte is not None and gte > lte:
            return {}
        return {k: v for k, v in (("gte", gte), ("lte", lte)) if v is not None}

    def error(self, qs: Any) -> str | None:
        if self._preset(qs) is not None:
            return None
        try:
            gte, lte = _parse_bounds(qs, self.field)
        except ValueError:
            return INVALID_DATE
        if gte is not None and lte is not None and gte > lte:
            return FROM_AFTER_TO
        return None

    def bounds(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> tuple[date | None, date | None]:
        """The resolved ``(from, to)`` dates, expanding a preset against today."""
        preset = parsed.get("preset")
        if preset is not None:
            period, offset, _label = PRESETS[preset]
            return period_bounds(period, (binding or FilterBinding()).today_date, offset)
        return parsed.get("gte"), parsed.get("lte")

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        gte, lte = self.bounds(parsed, binding)
        params = {
            suffix: value.isoformat()
            for suffix, value in (("gte", gte), ("lte", lte))
            if value is not None
        }
        return self.typed_conditions(binding, params) if params else []

    def describe(self, parsed: dict[str, Any]) -> str | None:
        preset = parsed.get("preset")
        if preset is not None:
            return PRESETS[preset][2].lower()
        gte, lte = parsed.get("gte"), parsed.get("lte")
        if gte is not None and lte is not None:
            return f"{gte.isoformat()} to {lte.isoformat()}"
        if gte is not None:
            return f"from {gte.isoformat()}"
        if lte is not None:
            return f"until {lte.isoformat()}"
        return None

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        parsed = base["parsed"]
        if parsed:
            gte, lte = self.bounds(parsed, ctx.binding)
            gte_raw = gte.isoformat() if gte else ""
            lte_raw = lte.isoformat() if lte else ""
        else:
            # Invalid input is echoed back so the user can fix it in place.
            gte_raw = query_value(ctx.query, f"{self.field}__gte") or ""
            lte_raw = query_value(ctx.query, f"{self.field}__lte") or ""
        base.update(
            gte=gte_raw,
            lte=lte_raw,
            preset=parsed.get("preset"),
            presets=[(name, PRESETS[name][2]) for name in self.presets],
        )
        return base


@dataclass(frozen=True, kw_only=True)
class CurrentPeriodDefault(FilterDef):
    """Preselect the current period on first load, until the user picks dates.

    Pairs with a :class:`DateRangeFilter` on the same field. When the
    querystring carries none of ``{field}__gte``/``__lte``/``__preset`` and not
    ``{field}=all``, the default applies: :meth:`compile` bounds the column to
    ``[first day of period, today]`` and :meth:`redirect_query` gives the
    querystring to push (``HX-Push-Url``) so the URL stays the source of truth.

    Args:
        period: ``"day"``, ``"week"``, ``"month"`` (default), ``"quarter"`` or ``"year"``.
    """

    template: ClassVar[str] = "components/filters/current_period.html"
    value_type: ClassVar[Any] = date

    period: Period = "month"

    def __post_init__(self) -> None:
        if self.period not in PERIOD_LABELS:
            msg = f"Unknown period {self.period!r}; expected one of {sorted(PERIOD_LABELS)}"
            raise ValueError(msg)

    @property
    def slug(self) -> str:
        return f"{self.field}-default"

    @property
    def query_keys(self) -> tuple[str, ...]:
        return (self.field, f"{self.field}__gte", f"{self.field}__lte", f"{self.field}__preset")

    def applies(self, qs: Any) -> bool:
        """``True`` when nothing in ``qs`` overrides the default."""
        if query_value(qs, self.field) == "all":
            return False
        return all(query_value(qs, key) is None for key in self.query_keys[1:])

    def parse(self, qs: Any) -> dict[str, Any]:
        return {"period": self.period} if self.applies(qs) else {}

    def default_bounds(self, binding: FilterBinding | None = None) -> tuple[date, date]:
        """``(first day of the period, today)``."""
        today = (binding or FilterBinding()).today_date
        return period_bounds(self.period, today)[0], today

    def default_params(self, binding: FilterBinding | None = None) -> dict[str, str]:
        """The ``{field}__gte``/``{field}__lte`` pair the default stands for."""
        start, today = self.default_bounds(binding)
        return {f"{self.field}__gte": start.isoformat(), f"{self.field}__lte": today.isoformat()}

    def redirect_query(self, qs: Any, binding: FilterBinding | None = None) -> str | None:
        """``qs`` plus the default bounds, URL-encoded, or ``None`` when the default is off."""
        if not self.applies(qs):
            return None
        return clear_href(qs, self.query_keys, self.default_params(binding))[1:]

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        if not parsed:
            return []
        start, today = self.default_bounds(binding)
        return self.typed_conditions(binding, {"gte": start.isoformat(), "lte": today.isoformat()})

    def describe(self, parsed: dict[str, Any]) -> str | None:
        return PERIOD_LABELS[self.period] if parsed else None

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        base.update(
            period_label=PERIOD_LABELS[self.period],
            show_all_href=clear_href(ctx.query, self.query_keys, {self.field: "all"}),
            default_query=urlencode(self.default_params(ctx.binding)),
        )
        return base
