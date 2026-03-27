from typing import Any

from pydantic import BaseModel
from sqlmodel import SQLModel


def get_display_name(instance: Any) -> str:
    """
    Returns a user-friendly string representation of a model instance.

    Logic:
    1. If the model has overridden __str__ from SQLModel/BaseModel, use it.
    2. Otherwise, look for common descriptive attributes: name, title, label, username, email.
    3. Fallback to "ModelName (PK)" if PK is available.
    4. Final fallback to "ModelName object".
    """
    cls = instance.__class__

    # Check if __str__ is overridden in the class or its bases
    # (excluding SQLModel, BaseModel, object)
    overridden = False
    for base in cls.__mro__:
        if base in (SQLModel, BaseModel, object):
            break
        if "__str__" in base.__dict__:
            overridden = True
            break

    if overridden:
        return str(instance)

    # Look for common descriptive attributes
    for attr in ("name", "title", "label", "username", "email"):
        if hasattr(instance, attr):
            val = getattr(instance, attr)
            if val is not None and val != "":
                return str(val)

    # Fallback to PK
    pk = getattr(instance, "id", None)
    if pk is not None:
        return f"{cls.__name__} ({pk})"

    return f"{cls.__name__} object"
