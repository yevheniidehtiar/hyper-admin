"""Seed-plan domain models.

A :class:`SeedPlan` is an ordered collection of :class:`TablePlan` entries. Order matters:
parents are seeded before children so the foreign-key pool is fully populated when a child
table starts. The plan is the single source of truth for what gets generated, in what
proportion, and how a resume run validates that the plan has not drifted.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hyperadmin.loadtest.pool import FKPool

# A row factory turns (fk pool, rng, global row sequence number) into a column->value dict.
# The sequence number is unique within the table and is used to make UNIQUE columns collision
# free (see ``TablePlan.unique_columns`` and the per-batch sequence prefix in ``batch.py``).
RowFactory = Callable[["FKPool", random.Random, int], dict[str, Any]]


@dataclass(frozen=True)
class TablePlan:
    """How to generate one table's rows.

    ``target_count`` doubles as the relative *weight* of the table: :meth:`SeedPlan.scaled`
    rescales every table's ``target_count`` proportionally so the totals sum to ``--count``.
    """

    name: str
    target_count: int
    row_factory: RowFactory
    columns: tuple[str, ...]
    fk_parents: tuple[str, ...] = ()
    unique_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.target_count < 0:
            raise ValueError(f"target_count for {self.name!r} must be >= 0")
        if not self.columns:
            raise ValueError(f"TablePlan {self.name!r} must declare its columns")
        missing = set(self.unique_columns) - set(self.columns)
        if missing:
            raise ValueError(
                f"unique_columns {sorted(missing)} of {self.name!r} are not in columns"
            )


@dataclass(frozen=True)
class SeedPlan:
    """An ordered set of table plans plus the FK skew parameter.

    The ordering invariant — every parent appears before the children that reference it — is
    validated at construction time. Violations raise :class:`ValueError` rather than failing
    obscurely at runtime when a child samples an empty pool.
    """

    tables: tuple[TablePlan, ...]
    pareto_a: float = 1.16

    def __post_init__(self) -> None:
        if not self.tables:
            raise ValueError("SeedPlan must contain at least one table")
        if self.pareto_a <= 0:
            raise ValueError("pareto_a must be > 0")
        seen: set[str] = set()
        for table in self.tables:
            for parent in table.fk_parents:
                if parent not in seen:
                    raise ValueError(
                        f"table {table.name!r} references parent {parent!r} "
                        "which is not seeded earlier in the plan"
                    )
            if table.name in seen:
                raise ValueError(f"duplicate table {table.name!r} in plan")
            seen.add(table.name)

    def table(self, name: str) -> TablePlan:
        """Return the table plan with ``name`` or raise ``KeyError``."""
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)

    def scaled(self, total_count: int) -> SeedPlan:
        """Return a copy whose per-table ``target_count`` values sum to ``total_count``.

        Every table is guaranteed **at least one row** (when ``total_count >= len(tables)``):
        a parent that scaled to zero would leave its children unable to sample a foreign key.
        One row per table is reserved first, then the remainder is distributed by weight using
        the largest-remainder method so the totals add up exactly with no drift.

        >>> from hyperadmin.loadtest.plan import SeedPlan, TablePlan
        >>> f = lambda pool, rng, seq: {"id": seq}
        >>> plan = SeedPlan(
        ...     (
        ...         TablePlan("a", 1, f, ("id",)),
        ...         TablePlan("b", 3, f, ("id",)),
        ...     )
        ... )
        >>> [t.target_count for t in plan.scaled(100).tables]
        [25, 75]
        """
        if total_count < 0:
            raise ValueError("total_count must be >= 0")
        weights = [t.target_count for t in self.tables]
        if sum(weights) == 0:
            raise ValueError("cannot scale a plan whose weights sum to 0")

        n = len(self.tables)
        if total_count == 0:
            counts = [0] * n
        elif total_count < n:
            raise ValueError(
                f"total_count ({total_count}) must be >= the number of tables ({n}) so every "
                "table — including FK parents — gets at least one row"
            )
        else:
            # Reserve one row per table, then apportion the rest by weight.
            remaining = total_count - n
            counts = [1 + extra for extra in _apportion(weights, remaining)]

        scaled_tables = tuple(
            _replace_count(table, count) for table, count in zip(self.tables, counts, strict=True)
        )
        return SeedPlan(scaled_tables, pareto_a=self.pareto_a)

    def hash(self) -> str:
        """Return a stable ``sha256:<hex>`` digest of the plan's structure.

        The digest covers table order, target counts, FK edges, unique columns, the declared
        column names per table, and ``pareto_a`` — everything whose change would invalidate an
        in-progress resume. The ``row_factory`` callables are deliberately excluded (they are
        not hashable and their column output is already captured by ``columns``).
        """
        canonical = {
            "pareto_a": self.pareto_a,
            "tables": [
                {
                    "name": t.name,
                    "target_count": t.target_count,
                    "columns": list(t.columns),
                    "fk_parents": list(t.fk_parents),
                    "unique_columns": list(t.unique_columns),
                }
                for t in self.tables
            ],
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


def _apportion(weights: list[int], total: int) -> list[int]:
    """Split ``total`` across ``weights`` by the largest-remainder method (sums to ``total``)."""
    weight_sum = sum(weights)
    if total == 0 or weight_sum == 0:
        return [0] * len(weights)
    exact = [w * total / weight_sum for w in weights]
    floored = [int(x) for x in exact]
    leftover = total - sum(floored)
    order = sorted(
        range(len(weights)),
        key=lambda i: (exact[i] - floored[i], weights[i]),
        reverse=True,
    )
    for i in order[:leftover]:
        floored[i] += 1
    return floored


def _replace_count(table: TablePlan, count: int) -> TablePlan:
    """Return ``table`` with ``target_count`` replaced (frozen dataclasses are immutable)."""
    return TablePlan(
        name=table.name,
        target_count=count,
        row_factory=table.row_factory,
        columns=table.columns,
        fk_parents=table.fk_parents,
        unique_columns=table.unique_columns,
    )


__all__ = ["RowFactory", "SeedPlan", "TablePlan"]
