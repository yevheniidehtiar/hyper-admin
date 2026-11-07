"""Compare-and-set version bump shared by the SQLModel and SQLAlchemy adapters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update as sa_update
from sqlalchemy.inspection import inspect as sa_inspect

from hyperadmin.adapters.introspection import coerce_column_value
from hyperadmin.core.concurrency import StaleRecordError, next_version


async def claim_version(
    session: Any, model: type, pk_attr: str, parsed_pk: Any, field: str, expected: Any
) -> Any:
    """Atomically bump ``field`` on one row iff it still equals ``expected``.

    Issues ``UPDATE ... SET field=next WHERE pk=:pk AND field=:expected`` so two writers
    holding the same version cannot both succeed. The caller applies the rest of the
    write in the same transaction.

    Returns:
        ``None`` if the row does not exist, otherwise the row with the bumped version.

    Raises:
        StaleRecordError: The stored version differs from ``expected``.
    """
    expected = coerce_column_value(sa_inspect(model), field, expected)
    stmt = (
        sa_update(model)
        .where(getattr(model, pk_attr) == parsed_pk, getattr(model, field) == expected)
        .values({field: next_version(field, expected)})
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        current = await session.get(model, parsed_pk, populate_existing=True)
        if current is None:
            return None
        raise StaleRecordError(
            model=model, pk=parsed_pk, expected=expected, current=getattr(current, field)
        )
    return await session.get(model, parsed_pk, populate_existing=True)
