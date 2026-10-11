"""Primary-key and datetime-kind introspection for mapped models.

Pure, read-only helpers built on SQLAlchemy mapper introspection. ORM adapters
(:mod:`hyperadmin.adapters.sqlmodel`, :mod:`hyperadmin.adapters.sqlalchemy`) use
these to build a model's :class:`~hyperadmin.core.primary_key.PrimaryKeyInfo`
and to answer :meth:`~hyperadmin.core.adapters.BaseAdapter.datetime_kind` from
actual column metadata, rather than from the pydantic annotation alone.
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from pydantic import AwareDatetime, NaiveDatetime
from pydantic_core import PydanticUndefined
from sqlalchemy import DateTime
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.types import TypeDecorator

from hyperadmin.core.primary_key import PrimaryKeyInfo

if TYPE_CHECKING:
    from hyperadmin.core.timezones import DateTimeKind

import sqlmodel.sql.sqltypes as _sqlmodel_sqltypes

#: ``UTCDateTime`` only exists from sqlmodel 0.0.45; ``getattr`` keeps this module
#: importable (and type-checkable) below that version, unlike a guarded import.
_SQLModelUTCDateTime: type | None = getattr(_sqlmodel_sqltypes, "UTCDateTime", None)


def _unwrap_optional(annotation: Any) -> Any:
    """Return ``annotation`` with a surrounding ``Optional[...]`` removed."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _model_field_annotation(model: Any, attr: str) -> Any:
    model_fields = getattr(model, "model_fields", None)
    if isinstance(model_fields, dict) and attr in model_fields:
        return model_fields[attr].annotation
    return None


def _resolve_python_type(model: Any, attr: str, column: Any) -> type:
    """Resolve the pk's Python type: annotation, then column type, then ``str``."""
    annotation = _unwrap_optional(_model_field_annotation(model, attr))
    if isinstance(annotation, type):
        return annotation
    try:
        return column.type.python_type
    except NotImplementedError:
        return str


def _has_non_none_default(model: Any, attr: str) -> bool:
    model_fields = getattr(model, "model_fields", None)
    if not isinstance(model_fields, dict) or attr not in model_fields:
        return False
    field_info = model_fields[attr]
    if getattr(field_info, "default_factory", None) is not None:
        return True
    default = field_info.default
    return default is not None and default is not PydanticUndefined


def _is_generated(
    model: Any, attr: str, column: Any, python_type: type, *, composite: bool
) -> bool:
    if column.autoincrement is True:
        return True
    is_int_type = (
        isinstance(python_type, type) and python_type is not bool and issubclass(python_type, int)
    )
    if column.autoincrement == "auto" and not composite and is_int_type:
        return True
    if column.default is not None or column.server_default is not None:
        return True
    return _has_non_none_default(model, attr)


def introspect_primary_key(model: Any) -> PrimaryKeyInfo:
    """Build a :class:`PrimaryKeyInfo` for ``model`` from mapper introspection.

    Resolves the mapped attribute key for each primary-key column (not
    necessarily the column name, e.g. ``sa_column=Column("id")`` mapped under
    attribute ``id_``), the Python type, whether the key is generated, and
    whether it is composite.
    """
    mapper = sa_inspect(model)
    pk_columns = mapper.primary_key
    attrs = tuple(mapper.get_property_by_column(col).key for col in pk_columns)
    composite = len(attrs) > 1
    attr = attrs[0]
    column = pk_columns[0]
    python_type = _resolve_python_type(model, attr, column)
    generated = _is_generated(model, attr, column, python_type, composite=composite)
    return PrimaryKeyInfo(
        attr=attr,
        python_type=python_type,
        generated=generated,
        composite=composite,
        attrs=attrs,
    )


def _annotation_aware_or_naive(annotation: Any) -> DateTimeKind | None:
    """Return ``"aware"``/``"naive"`` only for an explicit pydantic marker."""
    origin = get_origin(annotation)
    if origin is Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return _annotation_aware_or_naive(args[0])
        return None
    if annotation is AwareDatetime:
        return "aware"
    if annotation is NaiveDatetime:
        return "naive"
    return None


def datetime_kind(model: Any, field: str) -> DateTimeKind:
    """Return whether ``field`` stores timezone-aware or naive datetimes.

    The first matching rule wins:
      1. The pydantic annotation is ``AwareDatetime`` or ``NaiveDatetime``.
      2. The column type has ``hyperadmin_tz_aware = True``.
      3. The column type is sqlmodel's ``UTCDateTime`` (only when importable).
      4. The column type is ``DateTime(timezone=True)``, or a
         :class:`~sqlalchemy.types.TypeDecorator` whose ``impl.timezone`` is true.
      5. Otherwise ``"naive"``.
    """
    annotation_kind = _annotation_aware_or_naive(_model_field_annotation(model, field))
    if annotation_kind is not None:
        return annotation_kind

    mapper = sa_inspect(model)
    column = mapper.columns[field]
    column_type = column.type

    if getattr(column_type, "hyperadmin_tz_aware", False):
        return "aware"

    if _SQLModelUTCDateTime is not None and isinstance(column_type, _SQLModelUTCDateTime):
        return "aware"

    if isinstance(column_type, DateTime) and column_type.timezone:
        return "aware"
    if isinstance(column_type, TypeDecorator) and getattr(column_type.impl, "timezone", False):
        return "aware"

    return "naive"
