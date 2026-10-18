"""Declarative ``ReportView``: one grouped query, pivoted in memory.

A report is declared in code by subclassing :class:`ReportView`::

    class OrderRevenueReport(ReportView):
        slug = "orders-revenue"
        model = Order
        rows = [Group("sku")]
        cols = [TimeBucket("created_at", period="month")]
        values = [Sum("amount")]


    result = await OrderRevenueReport.run(session)
    grid = result.pivot()

Declaring ``cache = FactTableSource(model=OrderRevenueFact)`` makes the source
dispatcher read the same grouped query from the fact table instead of ``model``.

The caller owns the database session: :meth:`ReportView.run` takes an
``AsyncSession`` or a zero-argument session factory (e.g. an
``async_sessionmaker``) and never reaches for a module-level engine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import Select, func, inspect, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from hyperadmin.core.display import get_display_name, get_field_label
from hyperadmin_reports.aggregates import Aggregate, Many2One
from hyperadmin_reports.bucketing import Period, TimeBucket
from hyperadmin_reports.crosstab import Pivot, pivot

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapper
    from sqlalchemy.sql.elements import ColumnElement, Label

    from hyperadmin_reports.cache import FactTableSource

DateRange = tuple[date | datetime | str, date | datetime | str]
SessionSource = AsyncSession | Callable[[], AsyncSession]


class Group:
    """A report dimension grouping by the raw value of ``field``."""

    def __init__(self, field: str, *, label: str | None = None) -> None:
        self.field = field
        self._label = label

    @property
    def name(self) -> str:
        """Result-set key of this dimension."""
        return self.field

    @property
    def label(self) -> str:
        return self._label if self._label is not None else get_field_label(self.field)

    def __repr__(self) -> str:
        return f"Group({self.field!r})"


Dimension = Group | TimeBucket


@dataclass(frozen=True)
class ReportResult:
    """Flat grouped result of :meth:`ReportView.run`.

    ``records`` holds one mapping per ``(rows, cols)`` group, keyed by each
    dimension's and aggregate's ``name``. ``periods`` maps every
    :class:`TimeBucket` dimension to the concrete period it was run with
    (``auto`` already resolved).
    """

    records: list[dict[str, Any]]
    rows: list[str]
    cols: list[str]
    values: list[str]
    periods: dict[str, Period]
    fills: dict[str, Any]

    @property
    def columns(self) -> list[str]:
        return [*self.rows, *self.cols, *self.values]

    def pivot(self, value: str | None = None) -> Pivot:
        """Pivot one aggregate (default: the first) into a rows x cols grid."""
        name = value if value is not None else self.values[0]
        return pivot(
            self.records, rows=self.rows, cols=self.cols, value=name, fill=self.fills[name]
        )


class ReportView:
    """Base class for a declarative aggregated report over one model.

    ``filters`` is reserved for the v0.5.6 filter library integration and is
    not applied yet; until then callers narrow a report with ``run(where=...)``.
    ``cache`` swaps the queried table for a pre-built fact table.
    """

    slug: ClassVar[str] = ""
    label: ClassVar[str] = ""
    model: ClassVar[type[Any]]
    rows: ClassVar[Sequence[Dimension]] = ()
    cols: ClassVar[Sequence[Dimension]] = ()
    values: ClassVar[Sequence[Aggregate]] = ()
    filters: ClassVar[Sequence[Any] | None] = None
    cache: ClassVar[FactTableSource | None] = None
    permission: ClassVar[str | None] = None

    @classmethod
    def get_label(cls) -> str:
        return cls.label or cls.slug.replace("-", " ").replace("_", " ").capitalize()

    @classmethod
    def get_permission(cls) -> str:
        """Codename gating the report; default ``view_report_{slug}``."""
        return cls.permission or f"view_report_{cls.slug.replace('-', '_')}"

    @classmethod
    def source_model(cls) -> type[Any]:
        """The mapped class the report reads from: the cache's fact table, else ``model``."""
        return cls.cache.model if cls.cache is not None else cls.model

    @classmethod
    def validate(cls) -> None:
        """Raise ``ValueError`` if the declaration is inconsistent with ``model``."""
        if not cls.slug:
            raise ValueError(f"{cls.__name__}.slug is required")
        if getattr(cls, "model", None) is None:
            raise ValueError(f"{cls.__name__}.model is required")
        if not cls.values:
            raise ValueError(f"{cls.__name__}.values needs at least one aggregate")
        columns = set(_mapper(cls.model).columns.keys())
        fields = [d.field for d in (*cls.rows, *cls.cols)]
        fields += [a.field for a in cls.values if a.field != "*"]
        unknown = [f for f in fields if f not in columns]
        if unknown:
            raise ValueError(
                f"{cls.__name__} references unknown field(s) of {cls.model.__name__}: "
                + ", ".join(unknown)
            )
        if cls.cache is not None:
            cls.cache.validate(fields)
        names = [item.name for item in (*cls.rows, *cls.cols, *cls.values)]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(
                f"{cls.__name__} has duplicate column name(s): {', '.join(duplicates)}"
            )

    @classmethod
    def build_query(
        cls,
        dialect: str,
        periods: Mapping[str, Period],
        where: Sequence[ColumnElement[bool]] = (),
    ) -> Select[Any]:
        """The grouped ``SELECT`` for ``dialect``, with ``auto`` buckets resolved to ``periods``.

        The query reads from :meth:`source_model`; ``where`` clauses are applied
        before grouping, so they narrow the rows each aggregate sees.
        """
        dims = [(d.name, cls._dimension_expr(d, periods)) for d in (*cls.rows, *cls.cols)]
        aggs: list[Label[Any]] = [literal_column(a.sql(dialect)).label(a.name) for a in cls.values]
        exprs = [expr for _, expr in dims]
        return (
            select(*[expr.label(name) for name, expr in dims], *aggs)
            .select_from(cls.source_model())
            .where(*where)
            .group_by(*exprs)
            .order_by(*exprs)
        )

    @classmethod
    async def run(
        cls,
        session: SessionSource,
        *,
        date_range: DateRange | None = None,
        where: Sequence[ColumnElement[bool]] = (),
    ) -> ReportResult:
        """Execute the grouped query and return the flat result set.

        ``date_range`` (inclusive) drives ``TimeBucket(period="auto")``; without
        it the range is the bucketed column's min/max in the data. ``where``
        takes SQLAlchemy clauses built against :meth:`source_model`.
        """
        if isinstance(session, AsyncSession):
            return await cls._run(session, date_range, where)
        async with session() as owned:
            return await cls._run(owned, date_range, where)

    @classmethod
    async def _run(
        cls,
        session: AsyncSession,
        date_range: DateRange | None,
        where: Sequence[ColumnElement[bool]],
    ) -> ReportResult:
        cls.validate()
        dialect = session.get_bind().dialect.name
        periods: dict[str, Period] = {}
        for dim in (*cls.rows, *cls.cols):
            if isinstance(dim, TimeBucket):
                span = date_range
                if dim.period == "auto" and span is None:
                    span = await cls._data_range(session, dim.field, where)
                periods[dim.name] = dim.resolve_period(span)

        result = await session.execute(cls.build_query(dialect, periods, where))
        records = [dict(row._mapping) for row in result]
        for record in records:
            for name, period in periods.items():
                record[name] = TimeBucket.format_key(record[name], period)
        for agg in cls.values:
            if isinstance(agg, Many2One):
                await cls._resolve_many2one(session, agg, records)

        return ReportResult(
            records=records,
            rows=[d.name for d in cls.rows],
            cols=[d.name for d in cls.cols],
            values=[a.name for a in cls.values],
            periods=periods,
            fills={a.name: a.empty for a in cls.values},
        )

    @classmethod
    def _dimension_expr(cls, dim: Dimension, periods: Mapping[str, Period]) -> ColumnElement[Any]:
        column: ColumnElement[Any] = getattr(cls.source_model(), dim.field)
        if isinstance(dim, TimeBucket):
            return dim.expression(column, periods[dim.name])
        return column

    @classmethod
    async def _data_range(
        cls, session: AsyncSession, field: str, where: Sequence[ColumnElement[bool]]
    ) -> DateRange | None:
        column = getattr(cls.source_model(), field)
        query = select(func.min(column), func.max(column)).where(*where)
        low, high = (await session.execute(query)).one()
        if low is None or high is None:
            return None
        return (low, high)

    @classmethod
    async def _resolve_many2one(
        cls, session: AsyncSession, agg: Many2One, records: list[dict[str, Any]]
    ) -> None:
        """Replace FK ids in ``records[agg.name]`` with the related rows' display names."""
        target = agg.target or _fk_target(cls.model, agg.field)
        ids = {r[agg.name] for r in records if r[agg.name] is not None}
        if target is None or not ids:
            return
        target_mapper = _mapper(target)
        pk_column = target_mapper.primary_key[0]
        pk_attr = target_mapper.get_property_by_column(pk_column).key
        found = (await session.execute(select(target).where(pk_column.in_(ids)))).scalars()
        names = {getattr(obj, pk_attr): get_display_name(obj, pk_attr=pk_attr) for obj in found}
        for record in records:
            record[agg.name] = names.get(record[agg.name], record[agg.name])


def register_report(report: type[ReportView]) -> type[ReportView]:
    """Validate ``report`` (including its ``cache`` shape) and return it unchanged.

    Raises ``ValueError`` at registration time instead of on the first request;
    usable as a class decorator.
    """
    report.validate()
    return report


def _mapper(model: type[Any]) -> Mapper[Any]:
    return inspect(model)


def _fk_target(model: type[Any], field: str) -> type[Any] | None:
    """Mapped class of the table ``model.field`` references, if any."""
    mapper = _mapper(model)
    foreign_keys = mapper.columns[field].foreign_keys
    if not foreign_keys:
        return None
    table = next(iter(foreign_keys)).column.table
    for candidate in mapper.registry.mappers:
        if candidate.local_table is table:
            return candidate.class_
    return None
