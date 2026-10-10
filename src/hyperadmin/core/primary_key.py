"""Primary-key codec shared by adapters, routing and views.

``PrimaryKeyInfo`` describes a model's primary key (its attribute name and Python
type) and converts raw values — typically URL path segments or form fields — to
typed keys and back. It is pure: it uses pydantic ``TypeAdapter`` for lax
coercion and imports no ORM or HTTP code. Adapters build it through mapper
introspection; ``DEFAULT_PK`` keeps the historical ``int id`` behaviour for
adapters that do not set one.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic import TypeAdapter, ValidationError

PkKind = Literal["int", "uuid", "str", "other"]

_PATH_CONVERTORS: dict[PkKind, str] = {"int": "int", "uuid": "uuid"}
_CUSTOM_CONVERTOR = "hyperadmin_pk"


class InvalidPrimaryKey(ValueError):
    """Raised when a raw value cannot be parsed into a model's primary key."""


@lru_cache(maxsize=64)
def _type_adapter(python_type: type) -> TypeAdapter[Any]:
    return TypeAdapter(python_type)


@dataclass(frozen=True, slots=True)
class PrimaryKeyInfo:
    """Describes a model's primary key and converts values to and from it.

    Args:
        attr: The mapped attribute key (not necessarily the column name).
        python_type: ``int``, ``uuid.UUID``, ``str`` or another type.
        generated: Whether the database or model generates the key on insert.
        composite: Whether the key spans several columns (item routes unsupported).
        attrs: Every primary-key attribute; defaults to ``(attr,)``.
    """

    attr: str
    python_type: type
    generated: bool
    composite: bool = False
    attrs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.attrs:
            object.__setattr__(self, "attrs", (self.attr,))

    @property
    def kind(self) -> PkKind:
        """Return the coarse key kind used for routing and serialisation."""
        python_type = self.python_type
        # NewType, Optional[...] and other typing constructs are not classes.
        if python_type is bool or not isinstance(python_type, type):
            return "other"
        if issubclass(python_type, int):
            return "int"
        if issubclass(python_type, uuid.UUID):
            return "uuid"
        if issubclass(python_type, str):
            return "str"
        return "other"

    @property
    def path_convertor(self) -> str:
        """Return the Starlette path convertor name for item URLs."""
        return _PATH_CONVERTORS.get(self.kind, _CUSTOM_CONVERTOR)

    def parse(self, raw: Any) -> Any:
        """Convert ``raw`` into a typed key value.

        Raises:
            InvalidPrimaryKey: When ``raw`` is ``None``, empty or does not validate.
            NotImplementedError: For composite keys.
        """
        if self.composite:
            msg = "Composite primary keys are not supported for item operations"
            raise NotImplementedError(msg)
        if raw is None or (isinstance(raw, str) and raw == ""):
            msg = f"Empty primary key for {self.attr!r}"
            raise InvalidPrimaryKey(msg)
        if self.kind == "str" and isinstance(raw, int) and not isinstance(raw, bool):
            raw = str(raw)
        try:
            return _type_adapter(self.python_type).validate_python(raw)
        except ValidationError as exc:
            msg = f"Invalid primary key {raw!r} for {self.attr!r}"
            raise InvalidPrimaryKey(msg) from exc

    def to_str(self, value: Any) -> str:
        """Return the canonical string form (UUIDs lowercase and hyphenated)."""
        if self.kind == "uuid" and not isinstance(value, uuid.UUID):
            value = self.parse(value)
        return str(value)

    def to_json(self, value: Any) -> int | str:
        """Return a JSON-safe value; int keys stay numbers for popup back-compat."""
        if self.kind == "int":
            return int(self.parse(value))
        return self.to_str(value)

    def value_of(self, obj: Any) -> Any:
        """Read the key from a row mapping (``_pk`` first) or a model instance."""
        if isinstance(obj, Mapping):
            return obj.get("_pk", obj.get(self.attr))
        return getattr(obj, self.attr, None)


DEFAULT_PK = PrimaryKeyInfo(attr="id", python_type=int, generated=True)
