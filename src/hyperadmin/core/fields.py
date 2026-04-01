"""Field classification utilities for select widget auto-detection."""

from __future__ import annotations

import types as _types
from enum import Enum
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from hyperadmin.core.choices import SelectFieldMeta
from hyperadmin.core.uploads import FileFieldMeta


def _is_optional_union(origin: Any, args: tuple) -> bool:
    return (origin is Union or origin is _types.UnionType) and type(None) in args


if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

try:
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy.exc import NoInspectionAvailable

    _HAS_SQLALCHEMY = True
except ImportError:  # pragma: no cover
    _HAS_SQLALCHEMY = False
    sa_inspect = None  # type: ignore[assignment]
    NoInspectionAvailable = Exception  # type: ignore[assignment,misc]

try:
    from fastapi_storages.integrations.sqlalchemy import (
        FileType as _FileType,
    )
    from fastapi_storages.integrations.sqlalchemy import (
        ImageType as _ImageType,
    )

    _HAS_FILE_TYPES = True
except ImportError:  # pragma: no cover
    _HAS_FILE_TYPES = False
    _FileType = None  # type: ignore[assignment]
    _ImageType = None  # type: ignore[assignment]


def classify_field(
    field_info: FieldInfo,
    model_cls: type,
) -> SelectFieldMeta | FileFieldMeta | None:
    """Classify a Pydantic FieldInfo for widget auto-detection.

    Returns a ``SelectFieldMeta`` when the field should render as a
    select or multiselect widget, a ``FileFieldMeta`` when the
    underlying column is a ``FileType`` or ``ImageType``, or ``None``
    to fall through to existing widget logic.

    SQLAlchemy mapper inspection is isolated in a try/except so the
    function degrades gracefully when *model_cls* is a plain Pydantic
    model (no ORM).
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

    # Handle enum types (single or wrapped in a list)
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


def _inspect_orm_field(
    model_cls: type,
    field_name: str,
) -> SelectFieldMeta | FileFieldMeta | None:
    """Inspect the SQLAlchemy mapper for file/image columns and
    FK / M2M relations.

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

    if _HAS_FILE_TYPES:
        columns = getattr(mapper, "columns", [])
        for col in columns:
            if getattr(col, "key", None) == field_name:
                col_type = getattr(col, "type", None)
                if _ImageType is not None and isinstance(col_type, _ImageType):
                    return FileFieldMeta(is_image=True)
                if _FileType is not None and isinstance(col_type, _FileType):
                    return FileFieldMeta(is_image=False)

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
