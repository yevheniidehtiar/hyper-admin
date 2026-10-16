"""In-memory pivot of a flat grouped result set into a rows × columns grid.

The report runs one ``GROUP BY`` query over all row and column dimensions; the
pivot happens here, in Python, so no dialect-specific ``PIVOT`` / ``crosstab``
syntax is needed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Key = tuple[Any, ...]


def _sort_keys(keys: Iterable[Key]) -> list[Key]:
    """Sort dimension keys ascending, ``None`` last; keep first-seen order if unorderable."""
    unique = list(dict.fromkeys(keys))
    try:
        return sorted(unique, key=lambda k: tuple((v is None, v) for v in k))
    except TypeError:
        return unique


@dataclass(frozen=True)
class Pivot:
    """A pivoted grid.

    ``grid`` holds only the cells present in the data, keyed by the flat
    tuple ``(*row_key, *col_key)``; :meth:`cell` and :meth:`table` substitute
    ``fill`` for missing cells.
    """

    row_keys: list[Key]
    col_keys: list[Key]
    grid: dict[Key, Any]
    fill: Any = None
    rows: list[str] = field(default_factory=list)
    cols: list[str] = field(default_factory=list)

    def cell(self, row_key: Key, col_key: Key = ()) -> Any:
        """Value at ``(row_key, col_key)``, or ``fill`` if no data produced it."""
        return self.grid.get((*row_key, *col_key), self.fill)

    def table(self) -> list[list[Any]]:
        """Dense matrix: one list per row key, one value per column key."""
        return [[self.cell(r, c) for c in self.col_keys] for r in self.row_keys]


def pivot(
    records: Iterable[Mapping[str, Any]],
    *,
    rows: Sequence[str],
    cols: Sequence[str],
    value: str,
    fill: Any = None,
) -> Pivot:
    """Pivot ``records`` on ``rows`` × ``cols`` dimensions, taking ``value``.

    >>> p = pivot(
    ...     [{"sku": "A", "month": "2026-01", "total": 10}],
    ...     rows=["sku"],
    ...     cols=["month"],
    ...     value="total",
    ... )
    >>> p.grid
    {('A', '2026-01'): 10}

    Raises ``ValueError`` when two records share the same dimension key — the
    input must already be grouped on exactly ``rows + cols``.
    """
    grid: dict[Key, Any] = {}
    row_keys: list[Key] = []
    col_keys: list[Key] = []
    for record in records:
        row_key = tuple(record[name] for name in rows)
        col_key = tuple(record[name] for name in cols)
        key = (*row_key, *col_key)
        if key in grid:
            raise ValueError(f"Duplicate pivot cell {key!r}: records are not grouped by rows+cols")
        grid[key] = record[value]
        row_keys.append(row_key)
        col_keys.append(col_key)
    return Pivot(
        row_keys=_sort_keys(row_keys),
        col_keys=_sort_keys(col_keys) if cols else [()],
        grid=grid,
        fill=fill,
        rows=list(rows),
        cols=list(cols),
    )
