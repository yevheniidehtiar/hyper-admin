import logging
import sys
from enum import Enum
from typing import Any, Union, get_args, get_origin

if sys.version_info >= (3, 10):
    from types import UnionType
else:
    UnionType = Union  # type: ignore

from pydantic.fields import FieldInfo
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import NoInspectionAvailable

from hyperadmin.core.choices import SelectFieldMeta

logger = logging.getLogger(__name__)


def classify_field(field_info: FieldInfo, model_cls: type) -> SelectFieldMeta | None:
    """Classifies a model field to determine its widget and behavior.

    Args:
        field_info: Pydantic FieldInfo for the field.
        model_cls: The model class containing the field.

    Returns:
        SelectFieldMeta if the field is a choice field, otherwise None.
    """
    ann = getattr(field_info, "annotation", None)
    if ann is None:
        return None

    origin = get_origin(ann)
    args = get_args(ann)

    # Handle Optional[...] and T | None
    if (origin is Union or (sys.version_info >= (3, 10) and origin is UnionType)) and type(
        None
    ) in args:
        ann = next(arg for arg in args if arg is not type(None))
        origin = get_origin(ann)
        args = get_args(ann)

    # 1. Enum check
    if isinstance(ann, type) and issubclass(ann, Enum):
        return SelectFieldMeta(choices_source="enum", multiple=False, preload=True)

    # 2. list[Enum] check
    if origin is list and args and isinstance(args[0], type) and issubclass(args[0], Enum):
        return SelectFieldMeta(choices_source="enum", multiple=True, preload=True)

    # 3. SQLAlchemy/SQLModel relation check
    try:
        mapper: Any = sa_inspect(model_cls)
        # Check by name (the field name in Pydantic/SQLModel)
        # Note: SQLModel Relationship fields might not be in model_fields if they are not simple types,
        # but the prompt says classify_field(field_info, model_cls), so we assume the field IS in model_fields.
        # In SQLModel, Relationship names usually match the attribute name.
        field_name = None
        for name, info in getattr(model_cls, "model_fields", {}).items():
            if info is field_info:
                field_name = name
                break

        if field_name:
            rel = next((r for r in mapper.relationships if r.key == field_name), None)
            if rel:
                return SelectFieldMeta(
                    choices_source="relation",
                    multiple=rel.uselist,
                    preload=False,
                )

            # Check if it's a FK column
            fk_col = next((c for c in mapper.columns if c.key == field_name), None)
            if fk_col and fk_col.foreign_keys:
                return SelectFieldMeta(choices_source="relation", multiple=False, preload=False)

    except NoInspectionAvailable:
        pass

    # 4. list[str] static check
    if origin is list and args and args[0] is str:
        return SelectFieldMeta(choices_source="static", multiple=True, preload=True)

    # 5. Handle Optional[list[str]] case
    # If the annotation was Optional[list[str]], then ann is list[str] at this point.
    # The first handle Optional logic would have set ann = list[str], origin = list, args = (str,).
    # So the point 4 above should already handle it.
    # However, let's make sure by adding a check for the case where Optional was handled but it was not a simple list[str].

    return None
