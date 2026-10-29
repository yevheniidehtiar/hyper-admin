"""Build Pydantic schema classes from plain SQLAlchemy mapped classes.

SQLModel and Pydantic models are their own schema (identity in ``core.schema``). A
plain ``DeclarativeBase`` model has no ``model_fields``, so this module generates a
``pydantic.create_model`` class from its mapper: one field per single-column
``ColumnProperty``, with the annotation, optionality and defaults the views expect
(SDD ``docs/specs/sqlalchemy-field-metadata.md``). The builder is registered with
``schema_registry`` in :mod:`hyperadmin.adapters`.
"""

from __future__ import annotations

import inspect
import logging
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import Column, ColumnDefault, Integer, String
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import ColumnProperty, Mapped, Mapper
from sqlalchemy.sql.sqltypes import JSON
from sqlalchemy.sql.sqltypes import Enum as SAEnum
from sqlalchemy.types import TypeDecorator, TypeEngine

logger = logging.getLogger(__name__)


def is_sqlalchemy_mapped(model: object) -> bool:
    """Return ``True`` for a mapped SQLAlchemy class that is not a Pydantic model."""
    if not isinstance(model, type) or issubclass(model, BaseModel):
        return False
    return isinstance(sa_inspect(model, raiseerr=False), Mapper)


def _base_hints(base: type) -> dict[str, Any]:
    """Hints for one class: resolved when possible, else its non-string raw annotations."""
    try:
        return get_type_hints(base, include_extras=False)
    except Exception:
        raw = inspect.get_annotations(base)
        return {k: v for k, v in raw.items() if not isinstance(v, str)}


def _mapped_hints(model: type) -> dict[str, Any]:
    """Resolve type hints for ``model``, tolerating unresolvable forward references."""
    try:
        return get_type_hints(model, include_extras=False)
    except Exception:
        hints: dict[str, Any] = {}
        for base in reversed(model.__mro__):
            hints.update(_base_hints(base))
        return hints


def _strip_none(annotation: Any) -> Any:
    """Remove ``None`` from an optional union, leaving the other members."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        members = tuple(arg for arg in get_args(annotation) if arg is not type(None))
        if len(members) == 1:
            return members[0]
        return Union[members]  # noqa: UP007 - built dynamically from a tuple
    return annotation


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return (origin is Union or origin is types.UnionType) and type(None) in get_args(annotation)


def _is_sa_type(annotation: Any) -> bool:
    """Whether ``annotation`` is a SQLAlchemy type class such as a ``TypeDecorator``."""
    return isinstance(annotation, type) and issubclass(annotation, TypeEngine)


def _resolve_annotation(model: type, key: str, column: Column[Any], hints: dict[str, Any]) -> Any:
    """Pick the field annotation: ``Mapped[X]`` first, then the column's Python type."""
    hint = hints.get(key)
    if get_origin(hint) is Mapped:
        args = get_args(hint)
        # ``Mapped[GUID]`` names a SQLAlchemy type, not a Python one: use the column's.
        if args and not isinstance(args[0], str) and not _is_sa_type(_strip_none(args[0])):
            return _strip_none(args[0])
    sa_type = column.type
    if isinstance(sa_type, JSON):
        return dict | list | Any
    try:
        return sa_type.python_type
    except NotImplementedError:
        pass
    if isinstance(sa_type, TypeDecorator):
        try:
            return sa_type.impl_instance.python_type
        except NotImplementedError:
            pass
    logger.debug("No Python type for %s.%s (%r); using Any", model.__name__, key, sa_type)
    return Any


def _is_server_generated_pk(column: Column[Any], *, shared_pk: bool) -> bool:
    if not column.primary_key:
        return False
    if shared_pk:
        return True
    return isinstance(column.type, Integer) and column.autoincrement in (True, "auto")


def _default_kwargs(column: Column[Any], *, shared_pk: bool) -> dict[str, Any]:
    """Return ``default`` / ``default_factory`` kwargs, or ``{}`` when required."""
    if column.server_default is not None or _is_server_generated_pk(column, shared_pk=shared_pk):
        return {"default": None}
    default = column.default
    if isinstance(default, ColumnDefault):
        if default.is_scalar:
            return {"default": default.arg}
        if default.is_callable:
            # SQLAlchemy wraps context-free callables as ``lambda ctx: fn()`` and keeps
            # the original on ``__wrapped__``. A callable that needs the context
            # cannot run without a statement, so the ORM fills it in instead.
            original = getattr(default.arg, "__wrapped__", None)
            if original is not None:
                return {"default_factory": original}
        return {"default": None}
    if default is not None or column.nullable:
        return {"default": None}
    return {}


def _auto_now_hint(column: Column[Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if column.server_default is not None:
        kwargs["server_default"] = repr(getattr(column.server_default, "arg", None))
    if column.onupdate is not None:
        kwargs["onupdate"] = repr(getattr(column.onupdate, "arg", None))
    return {"sa_column_kwargs": kwargs} if kwargs else {}


def _column_for(prop: ColumnProperty[Any]) -> tuple[Column[Any], bool] | None:
    """Return ``(column, shared_pk)`` for a property that maps one editable column."""
    columns = prop.columns
    shared = len(columns) > 1 and all(getattr(c, "primary_key", False) for c in columns)
    if shared:
        # Joined-table inheritance: the subclass pk is the parent pk.
        columns = columns[:1]
    if len(columns) != 1 or not isinstance(columns[0], Column):
        return None
    return columns[0], shared


def build_sqlalchemy_schema(model: type) -> type[BaseModel]:
    """Generate a Pydantic class describing ``model``'s mapped columns."""
    mapper: Mapper[Any] = sa_inspect(model)
    hints = _mapped_hints(model)
    discriminator = mapper.polymorphic_on
    hide_discriminator = mapper.polymorphic_identity is not None and isinstance(
        discriminator, Column
    )
    fields: dict[str, Any] = {}
    for prop in mapper.column_attrs:
        # Deferred columns are declared "not loaded by default" (search vectors, blobs): reading
        # them on a row whose session has closed raises DetachedInstanceError.
        if prop.key.startswith("_") or prop.deferred:
            continue
        resolved = _column_for(prop)
        if resolved is None:
            continue
        column, shared_pk = resolved
        if hide_discriminator and column is discriminator:
            continue
        annotation = _resolve_annotation(model, prop.key, column, hints)
        kwargs = _default_kwargs(column, shared_pk=shared_pk)
        if (column.nullable or kwargs.get("default", 0) is None) and not _is_optional(annotation):
            annotation = annotation | None
        if (
            isinstance(column.type, String)
            and not isinstance(column.type, SAEnum)
            and column.type.length
            and annotation in (str, str | None)
        ):
            kwargs["max_length"] = column.type.length
        extra = _auto_now_hint(column)
        if extra:
            kwargs["json_schema_extra"] = extra
        fields[prop.key] = (annotation, Field(**kwargs))
    return create_model(  # type: ignore[call-overload,no-any-return]
        f"{model.__name__}Schema",
        __config__=ConfigDict(from_attributes=True, arbitrary_types_allowed=True),
        **fields,
    )
