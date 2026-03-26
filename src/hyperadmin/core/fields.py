"""Field classification utilities for select widget auto-detection."""

from __future__ import annotations

import sys
from enum import Enum
from typing import Any, Union, get_args, get_origin

# Python 3.10+ introduces X | Y union syntax (types.UnionType).  We must
# detect both typing.Union and types.UnionType when unwrapping Optional[X].
if sys.version_info >= (3, 10):
    import types as _types

    def _is_optional_union(origin: Any, args: tuple) -> bool:
        return (origin is Union or origin is _types.UnionType) and type(None) in args
else:

    def _is_optional_union(origin: Any, args: tuple) -> bool:
        return origin is Union and type(None) in args


from pydantic.fields import FieldInfo

from hyperadmin.core.choices import SelectFieldMeta

try:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.exc import NoInspectionAvailable

    _HAS_SQLALCHEMY = True
except ImportError:  # pragma: no cover
    _HAS_SQLALCHEMY = False
    sa_inspect = None  # type: ignore[assignment]
    NoInspectionAvailable = Exception  # type: ignore[assignment,misc]


def classify_field(field_info: FieldInfo, model_cls: type) -> SelectFieldMeta | None:
    """Classify a Pydantic FieldInfo for select widget auto-detection.

    Returns a ``SelectFieldMeta`` when the field should render as a select or
    multiselect widget. Returns ``None`` to fall through to existing widget logic.

    SQLAlchemy mapper inspection is isolated in a try/except so the function
    degrades gracefully when *model_cls* is a plain Pydantic model (no ORM).
    """
    ann = getattr(field_info, "annotation", None)
    if ann is None:
        return None

    # Unwrap Optional[X] → X  (handles both typing.Union and types.UnionType)
    origin = get_origin(ann)
    args = get_args(ann)
    if _is_optional_union(origin, args):
        ann = next(a for a in args if a is not type(None))
        origin = get_origin(ann)
        args = get_args(ann)

    # Detect list[X] wrapper
    is_list = origin is list
    inner = args[0] if (is_list and args) else ann

    # Enum or list[Enum]
    if isinstance(inner, type) and issubclass(inner, Enum):
        return SelectFieldMeta(
            choices_source="enum",
            preload=True,
            multiple=is_list,
        )

    # SQLAlchemy FK / M2M via mapper inspection
    field_name = _find_field_name(field_info, model_cls)
    if field_name is not None:
        meta = _inspect_orm_field(model_cls, field_name)
        if meta is not None:
            return meta

    # list[str] hybrid — no relation found
    if is_list and inner is str:
        return SelectFieldMeta(
            choices_source="static",
            preload=True,
            multiple=True,
        )

    return None


def _find_field_name(field_info: FieldInfo, model_cls: type) -> str | None:
    """Return the field name by identity-matching *field_info* in *model_cls.model_fields*."""
    model_fields = getattr(model_cls, "model_fields", {})
    for name, fi in model_fields.items():
        if fi is field_info:
            return name
    return None


def _inspect_orm_field(model_cls: type, field_name: str) -> SelectFieldMeta | None:
    """Inspect the SQLAlchemy mapper for FK / M2M relations.

    Returns ``None`` when *model_cls* has no SQLAlchemy mapper.
    """
    if not _HAS_SQLALCHEMY or sa_inspect is None:  # pragma: no cover
        return None

    try:
        mapper: Any = sa_inspect(model_cls)
    except NoInspectionAvailable:
        return None
    except Exception:
        return None

    relationships = getattr(mapper, "relationships", [])
    for rel in relationships:
        if getattr(rel, "key", None) == field_name:
            return SelectFieldMeta(
                choices_source="relation",
                preload=False,
                multiple=bool(getattr(rel, "uselist", False)),
            )

    columns = getattr(mapper, "columns", [])
    for col in columns:
        if getattr(col, "key", None) == field_name and getattr(col, "foreign_keys", None):
            return SelectFieldMeta(
                choices_source="relation",
                preload=True,  # FK columns are typically small; preload by default
                multiple=False,
            )

    return None
