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

``period="auto"`` is resolved per request by :func:`resolve_period`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, get_args

from sqlalchemy import Integer, String, cast, func, literal_column
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.functions import FunctionElement

from hyperadmin.core.display import get_field_label

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


def resolve_period(date_range: tuple[date | datetime | str, date | datetime | str]) -> Period:
    """Pick a bucket period for an inclusive ``(start, end)`` range.

    >>> resolve_period((date(2025, 1, 1), date(2025, 12, 31)))
    'quarter'
    """
    start, end = (_as_date(bound) for bound in date_range)
    days = abs((end - start).days) + 1
    for limit, period in AUTO_THRESHOLDS:
        if days <= limit:
            return period
    return "year"


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
        self, date_range: tuple[date | datetime | str, date | datetime | str] | None
    ) -> Period:
        """Concrete period for this bucket; ``auto`` needs a ``date_range``.

        A fixed period ignores the range. ``auto`` without a range (no data to
        span) collapses to ``year`` — a single bucket for any realistic set.
        """
        if self.period != "auto":
            return self.period
        if date_range is None:
            return "year"
        return resolve_period(date_range)

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
