import re
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlmodel import SQLModel

from hyperadmin.core.sensitive import effective_sensitive_field_names

_FK_SUFFIXES = ("_id", "_pk", "_fk")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def get_field_label(field_name: str) -> str:
    """Convert a field name to a human-readable label.

    - Strips ``_id`` / ``_pk`` / ``_fk`` suffix for FK fields, then title-cases.
    - Replaces ``_`` with space and title-cases for all other fields.

    Examples:
        >>> get_field_label("user_id")
        'User'
        >>> get_field_label("created_at")
        'Created At'
        >>> get_field_label("email")
        'Email'
    """
    label = field_name
    for suffix in _FK_SUFFIXES:
        if label.endswith(suffix):
            label = label[: -len(suffix)]
            break
    return label.replace("_", " ").title()


def humanize_class_name(name: str) -> str:
    """Split a CamelCase class name into sentence-case words.

    Examples:
        >>> humanize_class_name("InvoiceItem")
        'Invoice item'
        >>> humanize_class_name("HTTPLogEntry")
        'HTTP log entry'
    """
    first, *rest = _CAMEL_BOUNDARY.split(name)
    return " ".join([first, *(w if w.isupper() else w.lower() for w in rest)])


def pluralize(noun: str) -> str:
    """Return the English plural of ``noun`` (its last word) by the regular rules.

    Irregular nouns are out of scope: set ``verbose_name_plural`` for those.

    Examples:
        >>> [pluralize(n) for n in ("Item", "Address", "Box", "Journal entry", "Day")]
        ['Items', 'Addresses', 'Boxes', 'Journal entries', 'Days']
    """
    lower = noun.lower()
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return noun + "es"
    if len(noun) > 1 and lower.endswith("y") and lower[-2] not in "aeiou":
        return noun[:-1] + "ies"
    return noun + "s"


def _humanize_token(token: str) -> str:
    """``"to_pay"`` / ``"TO_PAY"`` / ``"to-pay"`` -> ``"To pay"``."""
    words = token.replace("_", " ").replace("-", " ").split()
    return " ".join(words).lower().capitalize()


def get_enum_label(member: Enum) -> str:
    """Return the human-readable label of an enum member.

    ``str(member)`` prints ``ContactType.CUSTOMER`` for a ``(str, Enum)`` on
    Python 3.11+, so it is never shown to users. The label is, in order:

    1. a string ``label`` attribute on the member (Django-style choices);
    2. the member's string value, as written when it has an uppercase letter
       or a space (``"Customer"``, ``"In progress"``), humanised when it is a
       lowercase slug (``"to_pay"`` -> ``"To pay"``);
    3. the member's name, humanised (``VERY_HIGH`` -> ``"Very high"``).

    Examples:
        >>> class Kind(str, Enum):
        ...     CUSTOMER = "Customer"
        ...     TO_PAY = "to_pay"
        >>> get_enum_label(Kind.CUSTOMER), get_enum_label(Kind.TO_PAY)
        ('Customer', 'To pay')
        >>> class Level(Enum):
        ...     VERY_HIGH = 3
        >>> get_enum_label(Level.VERY_HIGH)
        'Very high'
    """
    label = getattr(member, "label", None)
    if isinstance(label, str) and label:
        return label
    value = member.value
    if isinstance(value, str) and value.strip():
        if value != value.lower() or " " in value:
            return value
        return _humanize_token(value)
    return _humanize_token(member.name)


def get_display_name(instance: Any, *, pk_attr: str = "id") -> str:
    """
    Returns a user-friendly string representation of a model instance.

    Logic:
    1. If the model has overridden __str__ from SQLModel/BaseModel, use it.
    2. Otherwise, look for common descriptive attributes: name, title, label, username, email,
       skipping any that are sensitive (see :mod:`hyperadmin.core.sensitive`).
    3. Fallback to "ModelName (PK)", reading ``pk_attr`` (default ``"id"``, for
       models with a non-standard primary-key attribute).
    4. Final fallback to "ModelName object".

    The default ``__str__`` of SQLModel / Pydantic prints every field, secrets
    included, so it is never used: relation labels and list cells go through
    this function instead of ``str(instance)``.
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
    sensitive = effective_sensitive_field_names(cls)
    for attr in ("name", "title", "label", "username", "email"):
        if attr in sensitive:
            continue
        if hasattr(instance, attr):
            val = getattr(instance, attr)
            if val is not None and val != "":
                return str(val)

    # Fallback to PK
    pk = getattr(instance, pk_attr, None)
    if pk is not None:
        return f"{cls.__name__} ({pk})"

    return f"{cls.__name__} object"
