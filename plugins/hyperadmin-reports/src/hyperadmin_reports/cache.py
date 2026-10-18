"""Cached materialisation seam: read a report from a pre-built fact table.

A :class:`~hyperadmin_reports.view.ReportView` opts in by declaring
``cache = FactTableSource(model=OrderRevenueFact)``; the source dispatcher in
:meth:`ReportView.run` then queries the fact table instead of ``model`` with no
change to the calling code. The fact table is consumer-owned: HyperAdmin never
creates, migrates or refreshes it.

Aggregates are re-applied over the fact rows, so a pre-aggregated table only
reproduces the live result for re-aggregable values (``Sum`` of sums, ``Min``,
``Max``); a table at the live model's row grain reproduces every aggregate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect

if TYPE_CHECKING:
    from collections.abc import Iterable


class FactTableSource:
    """A consumer-owned mapped model holding pre-built report rows."""

    def __init__(self, model: type[Any]) -> None:
        self.model = model

    @property
    def columns(self) -> set[str]:
        """Column names of the fact table."""
        return set(inspect(self.model).columns.keys())

    def validate(self, fields: Iterable[str]) -> None:
        """Raise ``ValueError`` unless every report field is a fact-table column."""
        columns = self.columns
        missing = list(dict.fromkeys(f for f in fields if f not in columns))
        if len(missing) == 1:
            raise ValueError(f"FactTableSource missing column {missing[0]!r}")
        if missing:
            raise ValueError(
                "FactTableSource missing columns " + ", ".join(repr(m) for m in missing)
            )

    def __repr__(self) -> str:
        return f"FactTableSource(model={self.model.__name__})"
