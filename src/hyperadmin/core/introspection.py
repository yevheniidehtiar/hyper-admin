"""Model introspection utilities for zero-config auto-discovery.

Pure utility module that extracts field metadata from SQLModel/SQLAlchemy
models. Foundation for smart defaults (list_display, search_fields, list_filter)
and auto-discovery.

This module MUST NOT import from ``views/``, ``auth/``, or ``adapters/``.
"""

from __future__ import annotations

import types as _types
from dataclasses import dataclass
from enum import Enum
from typing import Any as _Any
from typing import Union, get_args, get_origin

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.sql.sqltypes import Text
from sqlmodel import SQLModel


@dataclass(frozen=True)
class FieldMeta:
    """Metadata about a single model field."""

    name: str
    python_type: type
    is_pk: bool = False
    is_fk: bool = False
    is_enum: bool = False
    is_nullable: bool = False
    max_length: int | None = None
    fk_target: str | None = None


def get_field_metadata(model: type[SQLModel]) -> dict[str, FieldMeta]:
    """Extract field metadata from a SQLModel table class.

    Args:
        model: A SQLModel class with ``table=True``.

    Returns:
        A dict mapping field names to their ``FieldMeta``.

    Raises:
        ValueError: If the model has no ``__tablename__`` (not a table model).
    """
    if not hasattr(model, "__table__"):
        msg = f"{model.__name__} is not a table model (missing table=True)"
        raise ValueError(msg)

    mapper: _Any = sa_inspect(model)
    result: dict[str, FieldMeta] = {}

    for col in mapper.columns:
        name = col.key
        ann = _get_python_type(model, name)

        is_pk = col.primary_key
        is_fk = bool(col.foreign_keys)
        fk_target = None
        if is_fk:
            fk = next(iter(col.foreign_keys))
            fk_target = fk.column.table.name

        is_enum = isinstance(ann, type) and issubclass(ann, Enum)
        is_nullable = col.nullable or False
        max_length = getattr(col.type, "length", None)

        result[name] = FieldMeta(
            name=name,
            python_type=ann,
            is_pk=is_pk,
            is_fk=is_fk,
            is_enum=is_enum,
            is_nullable=is_nullable,
            max_length=max_length,
            fk_target=fk_target,
        )

    return result


def _get_python_type(model: type[SQLModel], field_name: str) -> type:
    """Resolve the Python type of a model field, unwrapping Optional."""
    model_fields = getattr(model, "model_fields", {})
    field_info = model_fields.get(field_name)
    if field_info is None:
        return object

    ann = getattr(field_info, "annotation", None)
    if ann is None:
        return object

    origin = get_origin(ann)
    args = get_args(ann)
    if (origin is Union or origin is _types.UnionType) and type(None) in args:
        return next(a for a in args if a is not type(None))

    return ann if isinstance(ann, type) else object


# ── Priority lists for smart defaults ──────────────────────────────────

_NAME_FIELDS = {"name", "title", "label", "username", "slug"}
_EMAIL_FIELDS = {"email", "email_address"}
_TIMESTAMP_FIELDS = {"created_at", "updated_at", "created", "modified"}
_STATUS_FIELDS = {"status", "state", "is_active", "is_enabled"}
_LONG_TEXT_NAMES = {"bio", "description", "body", "content", "notes", "text", "summary"}


def _is_long_text(model: type[SQLModel], field_name: str) -> bool:
    """Check if a column uses SQL Text type or has a long-text name."""
    if field_name in _LONG_TEXT_NAMES:
        return True
    try:
        mapper: _Any = sa_inspect(model)
        col = mapper.columns.get(field_name)
        if col is not None and isinstance(col.type, Text):
            return True
    except Exception:
        return False
    return False


def _field_priority(name: str, fm: FieldMeta) -> int:
    """Return sort key for display priority (lower = higher priority)."""
    if fm.is_pk:
        return 0
    if name in _NAME_FIELDS:
        return 1
    if name in _EMAIL_FIELDS:
        return 2
    if name in _TIMESTAMP_FIELDS:
        return 3
    if name in _STATUS_FIELDS or fm.is_enum:
        return 4
    if fm.is_fk:
        return 6
    return 5


def infer_list_display(model: type[SQLModel]) -> list[str]:
    """Infer 3-5 fields for list view display via heuristics.

    Priority: id > name/title > email > created_at > status/enum > other short fields.
    Long text fields (Text type, bio, description) are excluded.
    Cap at 5 fields.
    """
    meta = get_field_metadata(model)
    if not meta:
        return ["id", "__str__"]

    candidates = [
        (name, fm) for name, fm in meta.items() if not _is_long_text(model, name) or fm.is_pk
    ]
    candidates.sort(key=lambda pair: _field_priority(pair[0], pair[1]))

    result = [name for name, _ in candidates[:5]]

    if not result or result == ["id"]:
        return ["id", "__str__"]

    return result


def infer_search_fields(model: type[SQLModel]) -> list[str]:
    """Infer searchable fields — string/email/text fields only.

    FK, numeric, boolean, binary fields are excluded.
    Returns ``[]`` when no string fields exist.
    """
    meta = get_field_metadata(model)
    result: list[str] = []

    for name, fm in meta.items():
        if fm.is_pk or fm.is_fk or fm.is_enum:
            continue
        if fm.python_type is str:
            result.append(name)

    return result


def infer_list_filter(model: type[SQLModel]) -> list[str]:
    """Infer filterable fields — boolean, enum, and FK fields.

    String, text, numeric-only fields are excluded.
    Returns ``[]`` when no filterable fields exist.
    """
    meta = get_field_metadata(model)
    result: list[str] = []

    for name, fm in meta.items():
        if fm.is_pk:
            continue
        if fm.python_type is bool or fm.is_enum or fm.is_fk:
            result.append(name)

    return result


def discover_sqlmodel_models() -> list[type]:
    """Discover all user-defined SQLModel table models.

    Walks SQLModel's metadata registry and returns model classes,
    excluding HyperAdmin internal models (``hyperadmin.*``) and
    abstract models without ``table=True``.

    Returns:
        A list of SQLModel table model classes.
    """
    models: list[type] = []
    seen_tables: set[str] = set()

    for mapper in SQLModel.__subclasses__():
        _collect_table_models(mapper, models, seen_tables)

    return models


def _collect_table_models(cls: type, models: list[type], seen_tables: set[str]) -> None:
    """Recursively collect table models from a class hierarchy."""
    # Check subclasses first (depth-first)
    for sub in cls.__subclasses__():
        _collect_table_models(sub, models, seen_tables)

    # Skip non-table models (only table=True models have __table__)
    if not hasattr(cls, "__table__"):
        return

    # Skip HyperAdmin internal models
    module = getattr(cls, "__module__", "") or ""
    if module.startswith("hyperadmin"):
        return

    # Deduplicate by table name
    tablename: str = getattr(cls, "__tablename__", "")
    if tablename in seen_tables:
        return
    seen_tables.add(tablename)

    models.append(cls)
