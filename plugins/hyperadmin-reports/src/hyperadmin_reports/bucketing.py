"""Time-series bucketing for report dimensions.

A :class:`TimeBucket` groups a date/datetime column into ``day`` / ``week`` /
``month`` / ``quarter`` / ``year`` buckets. Bucket keys are computed in SQL so
grouping happens in the database; they are sortable strings:

=========  ================  ======================================
period     key in SQL        label (:meth:`TimeBucket.format_key`)
=========  ================  ======================================
day        ``2026-01-15``    ``2026-01-15``
week       ``2026-01-12``    ``2026-W03`` (ISO week; key is Monday)
month      ``2026-01``       ``2026-01``
quarter    ``2026-Q1``       ``2026-Q1``
year       ``2026``          ``2026``
=========  ================  ======================================

``period="auto"`` is resolved per request by :func:`resolve_period`; a report
page may override any declared period with ``?period=`` (see
:meth:`TimeBucket.resolve_period`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal, get_args

from sqlalchemy import Integer, String, cast, func, literal_column
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from hyperadmin.core.display import get_field_label

if TYPE_CHECKING:
    from sqlalchemy.sql.compiler import SQLCompiler
    from sqlalchemy.sql.elements import ColumnElement

Period = Literal["day", "week", "month", "quarter", "year"]
PeriodOrAuto = Literal["day", "week", "month", "quarter", "year", "auto"]

PERIODS: tuple[Period, ...] = get_args(Period)

#: ``period="auto"`` thresholds: the first period whose limit (inclusive days in
#: the requested range) is not exceeded wins; longer ranges bucket by year.
AUTO_THRESHOLDS: tuple[tuple[int, Period], ...] = (
    (31, "day"),
    (92, "week"),
    (186, "month"),
    (1100, "quarter"),
)


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def range_days(date_range: tuple[date | datetime | str, date | datetime | str]) -> int:
    """Inclusive number of days an ``(start, end)`` range spans.

    >>> range_days((date(2025, 1, 1), date(2025, 1, 31)))
    31
    """
    start, end = (_as_date(bound) for bound in date_range)
    return abs((end - start).days) + 1


def period_for_days(days: int) -> Period:
    """The ``auto`` bucket for a range of ``days`` days (see :data:`AUTO_THRESHOLDS`)."""
    for limit, period in AUTO_THRESHOLDS:
        if days <= limit:
            return period
    return "year"


def resolve_period(date_range: tuple[date | datetime | str, date | datetime | str]) -> Period:
    """Pick a bucket period for an inclusive ``(start, end)`` range.

    >>> resolve_period((date(2025, 1, 1), date(2025, 12, 31)))
    'quarter'
    """
    return period_for_days(range_days(date_range))


def describe_span(days: int) -> str:
    """Human-readable length of a ``days``-day range, for the "Auto chose ..." note.

    Up to the week threshold the note counts days; beyond it, whole months.

    >>> describe_span(45)
    '45-day'
    >>> describe_span(365)
    '12-month'
    """
    if days <= AUTO_THRESHOLDS[1][0]:
        return f"{days}-day"
    return f"{max(1, round(days / _DAYS_PER_MONTH))}-month"


_DAYS_PER_MONTH = 30.4375


class TimeBucket:
    """A report dimension that groups ``field`` into time buckets."""

    def __init__(
        self, field: str, *, period: PeriodOrAuto = "month", label: str | None = None
    ) -> None:
        if period != "auto" and period not in PERIODS:
            raise ValueError(f"Unknown TimeBucket period {period!r}")
        self.field = field
        self.period: PeriodOrAuto = period
        self._label = label

    @property
    def name(self) -> str:
        """Result-set key of this dimension."""
        return self.field

    @property
    def label(self) -> str:
        return self._label if self._label is not None else get_field_label(self.field)

    def resolve_period(
        self,
        date_range: tuple[date | datetime | str, date | datetime | str] | None,
        override: PeriodOrAuto | None = None,
    ) -> Period:
        """Concrete period for this bucket; ``auto`` needs a ``date_range``.

        ``override`` (the page's ``?period=``) replaces the declared period for
        this request. A fixed period ignores the range. ``auto`` without a range
        (no data to span) collapses to ``year`` — a single bucket for any
        realistic set.
        """
        period = override if override is not None else self.period
        if period != "auto":
            return period
        if date_range is None:
            return "year"
        return resolve_period(date_range)

    @staticmethod
    def split_key(key: Any, period: Period) -> tuple[str | None, str]:
        """``(year, short label)`` of a formatted bucket key, for two-level headers.

        Sub-year buckets abbreviate to what the year does not already say:
        ``"2025-Q1"`` → ``("2025", "Q1")``, ``"2026-W03"`` → ``("2026", "W03")``,
        ``"2026-01-15"`` → ``("2026", "01-15")``. Month keys keep their full
        label (``"2026-01"``) and a ``year`` bucket has no parent level.

        >>> TimeBucket.split_key("2025-Q3", "quarter")
        ('2025', 'Q3')
        """
        text = "" if key is None else str(key)
        if period == "year" or len(text) < _YEAR_PREFIX_LEN:
            return (None, text)
        year = text[: _YEAR_PREFIX_LEN - 1]
        return (year, text if period == "month" else text[_YEAR_PREFIX_LEN:])

    def expression(self, column: ColumnElement[Any], period: Period) -> ColumnElement[str]:
        """SQL expression computing the bucket key of ``column``."""
        return _BucketKey(column, period)

    @staticmethod
    def format_key(key: Any, period: Period) -> Any:
        """Display label for a bucket key returned by the database."""
        if period == "week" and key is not None:
            year, week, _ = _as_date(key).isocalendar()
            return f"{year}-W{week:02d}"
        return key

    def __repr__(self) -> str:
        return f"TimeBucket({self.field!r}, period={self.period!r})"


_YEAR_PREFIX_LEN = len("2026-")


class _BucketKey(FunctionElement[str]):
    """Dialect-dispatched bucket key; see :class:`TimeBucket`."""

    name = "bucket_key"
    type = String()
    inherit_cache = False

    def __init__(self, column: ColumnElement[Any], period: Period) -> None:
        super().__init__(column)
        self.period: Period = period

    @property
    def column(self) -> ColumnElement[Any]:
        return next(iter(self.clauses))  # type: ignore[no-any-return]


# Format strings are inlined (``literal_column``) rather than bound: PostgreSQL
# treats ``to_char(col, $1)`` in SELECT and ``to_char(col, $2)`` in GROUP BY as
# different expressions and rejects the query.

_PG_FORMATS: dict[Period, str] = {
    "day": "'YYYY-MM-DD'",
    "month": "'YYYY-MM'",
    "quarter": "'YYYY-\"Q\"Q'",
    "year": "'YYYY'",
}

_SQLITE_FORMATS: dict[Period, str] = {
    "day": "'%Y-%m-%d'",
    "month": "'%Y-%m'",
    "year": "'%Y'",
}

_MYSQL_FORMATS: dict[Period, str] = {
    "day": "'%Y-%m-%d'",
    "month": "'%Y-%m'",
    "year": "'%Y'",
}


@compiles(_BucketKey, "postgresql")
def _compile_postgresql(element: _BucketKey, compiler: SQLCompiler, **kw: Any) -> str:
    col = element.column
    if element.period == "week":
        expr = func.to_char(
            func.date_trunc(literal_column("'week'"), col), literal_column(_PG_FORMATS["day"])
        )
    else:
        expr = func.to_char(col, literal_column(_PG_FORMATS[element.period]))
    return compiler.process(expr, **kw)


@compiles(_BucketKey, "sqlite")
def _compile_sqlite(element: _BucketKey, compiler: SQLCompiler, **kw: Any) -> str:
    col = element.column
    if element.period == "week":
        # 'weekday 0' advances to Sunday (same day if already Sunday); -6 days → Monday.
        expr: ColumnElement[Any] = func.date(
            col, literal_column("'weekday 0'"), literal_column("'-6 days'")
        )
    elif element.period == "quarter":
        month = cast(func.strftime(literal_column("'%m'"), col), Integer)
        expr = (
            func.strftime(literal_column("'%Y'"), col, type_=String)
            + literal_column("'-Q'", String)
            + cast((month + literal_column("2", Integer)) // literal_column("3", Integer), String)
        )
    else:
        expr = func.strftime(literal_column(_SQLITE_FORMATS[element.period]), col)
    return compiler.process(expr, **kw)


@compiles(_BucketKey, "mysql")
@compiles(_BucketKey, "mariadb")
def _compile_mysql(element: _BucketKey, compiler: SQLCompiler, **kw: Any) -> str:
    col = element.column
    if element.period == "week":
        monday = func.date_sub(
            col, literal_column(f"INTERVAL WEEKDAY({compiler.process(col, **kw)}) DAY")
        )
        expr: ColumnElement[Any] = func.date_format(monday, literal_column(_MYSQL_FORMATS["day"]))
    elif element.period == "quarter":
        expr = func.concat(func.year(col), literal_column("'-Q'"), func.quarter(col))
    else:
        expr = func.date_format(col, literal_column(_MYSQL_FORMATS[element.period]))
    return compiler.process(expr, **kw)


@compiles(_BucketKey)
def _compile_default(element: _BucketKey, compiler: SQLCompiler, **kw: Any) -> str:
    raise NotImplementedError(
        f"TimeBucket has no SQL for dialect {compiler.dialect.name!r}; "
        "supported: postgresql, sqlite, mysql/mariadb"
    )
