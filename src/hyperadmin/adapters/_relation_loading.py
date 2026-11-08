"""Eager-loading options shared by the SQLAlchemy-based adapters."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload


def relation_load_options(model: Any, names: Sequence[str]) -> list[Any]:
    """Return a ``selectinload`` option per relation in ``names``.

    Raises:
        ValueError: When a name is not a relationship of ``model``.
    """
    known = {rel.key for rel in inspect(model).relationships}
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ValueError(
            f"Unknown relation(s) {', '.join(map(repr, unknown))} on {model.__name__}; "
            f"expected one of {sorted(known)}"
        )
    return [selectinload(getattr(model, name)) for name in dict.fromkeys(names)]
