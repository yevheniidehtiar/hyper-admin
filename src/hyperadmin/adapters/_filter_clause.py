"""Shared SQLAlchemy clause-building for typed filter conditions (st-v058-byoa-24).

``SQLModelAdapter.list`` and ``SQLAlchemyAdapter.list`` both resolve their
``filters`` argument (a legacy ``dict`` or a ``Sequence[FilterCondition]``) to
:class:`~hyperadmin.core.filtering.FilterCondition` objects via
:func:`hyperadmin.core.filtering.normalize_filters`, then compile each one to a
SQLAlchemy boolean clause through this single, shared implementation — so a
range or ``isnull`` condition compiles identically for both ORMs instead of
drifting between two hand-written copies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hyperadmin.core.filtering import MAX_IN_VALUES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import ColumnElement

    from hyperadmin.core.filtering import FilterCondition


def build_clause(model: Any, condition: FilterCondition) -> ColumnElement[bool]:
    """Compile one :class:`FilterCondition` to a SQLAlchemy boolean clause.

    Args:
        model: The mapped class ``condition.field`` is resolved against.
        condition: The typed predicate to compile.

    Returns:
        A clause suitable for ``Select.where()``.

    Raises:
        ValueError: When an ``in`` condition carries more than
            ``MAX_IN_VALUES`` values. ``parse_filter_params`` already caps
            query-string input to this limit; this guards library callers
            that build a :class:`FilterCondition` directly, so they get a
            clear error instead of a driver-level failure.
    """
    column = getattr(model, condition.field)
    op = condition.op
    if op == "exact":
        return column == condition.value
    if op == "gte":
        return column >= condition.value
    if op == "lte":
        return column <= condition.value
    if op == "in":
        if len(condition.value) > MAX_IN_VALUES:
            msg = f"Too many values for {condition.field} (max {MAX_IN_VALUES})"
            raise ValueError(msg)
        return column.in_(condition.value)
    # op == "isnull" — FilterCondition.__post_init__ guarantees one of the five
    # FilterOp values, so this is the only case left.
    return column.is_(None) if condition.value else column.is_not(None)


def build_clauses(model: Any, conditions: Sequence[FilterCondition]) -> list[ColumnElement[bool]]:
    """Compile every condition in ``conditions`` to a clause, in order."""
    return [build_clause(model, condition) for condition in conditions]
