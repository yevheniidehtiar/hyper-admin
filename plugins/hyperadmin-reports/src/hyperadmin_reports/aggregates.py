"""Declarative report aggregates.

Each aggregate renders its own per-dialect SQL via :meth:`Aggregate.sql`; the
grouped query in :mod:`hyperadmin_reports.view` executes exactly that text, so
the documented SQL and the executed SQL never drift apart.
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.dialects import registry
from sqlalchemy.exc import NoSuchModuleError

from hyperadmin.core.display import get_field_label

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.engine import Dialect

_COMMA = ", "


@cache
def _dialect(name: str) -> Dialect:
    """Instantiate a SQLAlchemy dialect by name (``"postgresql"``, ``"sqlite"``, ...)."""
    # MariaDB's registry entry is a factory over an engine URL; quoting is MySQL's.
    try:
        dialect_cls = registry.load("mysql" if name == "mariadb" else name)
    except NoSuchModuleError as exc:
        raise ValueError(f"Unknown SQL dialect: {name!r}") from exc
    return dialect_cls()


def _quote(field: str, dialect: str) -> str:
    """Always-quoted identifier for ``field`` in ``dialect``."""
    return _dialect(dialect).identifier_preparer.quote_identifier(field)


class Aggregate:
    """Base class for a single aggregated value column of a report.

    Subclasses set :attr:`function` (the SQL aggregate name) and may override
    :meth:`sql` for dialect-specific syntax. :attr:`empty` is the value a pivot
    cell takes when no row contributed to it. :attr:`totals` says whether the
    report page and exports show row, column and grand totals for it
    (:meth:`total`): sums, counts, minima and maxima can be folded, a
    comma-joined list or a related record cannot.
    """

    function: ClassVar[str]
    title: ClassVar[str]
    empty: ClassVar[Any] = None
    totals: ClassVar[bool] = False

    def __init__(self, field: str, *, label: str | None = None) -> None:
        self.field = field
        self._label = label

    @property
    def name(self) -> str:
        """Result-set key of this aggregate, e.g. ``"sum_amount"``."""
        suffix = "all" if self.field == "*" else self.field
        return f"{self.function.lower()}_{suffix}"

    @property
    def label(self) -> str:
        """Human-readable column header, e.g. ``"Sum of Amount"``."""
        if self._label is not None:
            return self._label
        target = "Rows" if self.field == "*" else get_field_label(self.field)
        return f"{self.title} of {target}"

    def sql(self, dialect: str) -> str:
        """Return the aggregate SQL expression for ``dialect``.

        >>> Sum("amount").sql("postgresql")
        'SUM("amount")'
        """
        return f"{self.function}({_quote(self.field, dialect)})"

    def total(self, values: Iterable[Any]) -> Any:
        """Fold pivot cells into one total, or ``None`` when nothing can be totalled.

        Empty cells (``None``) are skipped; an all-empty line totals to ``None``,
        never to a printed zero.
        """
        if not self.totals:
            return None
        present = [v for v in values if v is not None]
        return self._fold(present) if present else None

    def _fold(self, values: list[Any]) -> Any:
        return sum(values)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.field!r})"


class Sum(Aggregate):
    """``SUM(field)`` — empty cells are ``None`` (no rows is not the same as zero)."""

    function = "SUM"
    title = "Sum"
    totals = True


class Count(Aggregate):
    """``COUNT(field)``, or ``COUNT(*)`` for ``Count()`` — empty cells are ``0``."""

    function = "COUNT"
    title = "Count"
    empty = 0
    totals = True

    def __init__(self, field: str = "*", *, label: str | None = None) -> None:
        super().__init__(field, label=label)

    def sql(self, dialect: str) -> str:
        if self.field == "*":
            return "COUNT(*)"
        return super().sql(dialect)


class Min(Aggregate):
    """``MIN(field)`` — its total is the smallest minimum."""

    function = "MIN"
    title = "Min"
    totals = True

    def _fold(self, values: list[Any]) -> Any:
        return min(values)


class Max(Aggregate):
    """``MAX(field)`` — its total is the largest maximum."""

    function = "MAX"
    title = "Max"
    totals = True

    def _fold(self, values: list[Any]) -> Any:
        return max(values)


class StringAggComma(Aggregate):
    """Comma-separated concatenation of the group's values (order unspecified)."""

    function = "STRING_AGG"
    title = "List"

    def sql(self, dialect: str) -> str:
        column = _quote(self.field, dialect)
        if dialect == "postgresql":
            return f"STRING_AGG(CAST({column} AS TEXT), '{_COMMA}')"
        if dialect == "sqlite":
            return f"GROUP_CONCAT({column}, '{_COMMA}')"
        if dialect in ("mysql", "mariadb"):
            return f"GROUP_CONCAT({column} SEPARATOR '{_COMMA}')"
        raise ValueError(f"StringAggComma has no SQL for dialect {dialect!r}")


class Many2One(Aggregate):
    """The group's foreign-key value, rendered as the related row's display.

    The query selects ``MAX(fk)`` (constant within a group keyed on the FK's
    owner); :meth:`hyperadmin_reports.ReportView.run` then swaps each id for
    the related row's display name, falling back to the raw pk when the
    target model is unknown or the row no longer exists.

    ``target`` is the related model; when omitted it is inferred from the
    column's ``ForeignKey``.
    """

    function = "MAX"
    title = "Many2One"

    def __init__(
        self, field: str, *, target: type[Any] | None = None, label: str | None = None
    ) -> None:
        super().__init__(field, label=label)
        self.target = target

    @property
    def name(self) -> str:
        return self.field

    @property
    def label(self) -> str:
        return self._label if self._label is not None else get_field_label(self.field)
