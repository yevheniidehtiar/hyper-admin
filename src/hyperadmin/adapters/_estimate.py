"""Cheap whole-table row counts shared by the SQLModel and SQLAlchemy adapters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Table, func, select, text


async def estimate_table_rows(session: Any, table: Table) -> tuple[int, bool]:
    """Return ``(rows, is_estimate)`` for ``table``.

    PostgreSQL answers from planner statistics (``pg_class.reltuples``), which costs one
    catalog lookup however large the table is. The statistic is ``-1`` (newer servers) or
    ``0`` (older ones) for a table that was never analyzed, and ``0`` right after a bulk
    load, so a value of zero or less falls through to the exact count. Every other dialect
    has no such catalog and counts exactly, which is acceptable for the small tables the
    result is used to classify.

    The table name is passed as a bound ``regclass`` parameter, schema-qualified and quoted
    by the dialect, never interpolated into the SQL text.
    """
    dialect = (await session.connection()).dialect
    if dialect.name == "postgresql":
        qualified = dialect.identifier_preparer.format_table(table)
        statement = text(
            "SELECT reltuples::bigint FROM pg_class WHERE oid = CAST(:tbl AS regclass)"
        )
        estimate = (await session.execute(statement, {"tbl": qualified})).scalar_one_or_none()
        if estimate is not None and estimate > 0:
            return int(estimate), True
    exact = (await session.execute(select(func.count()).select_from(table))).scalar_one()
    return int(exact), False
