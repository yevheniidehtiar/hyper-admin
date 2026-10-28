"""Schema registry: one seam that answers "what are this model's fields".

Views and adapters ask ``schema_for(model)`` for a Pydantic class describing the
model's editable fields. ``BaseModel`` subclasses (Pydantic, SQLModel) are their own
schema. Other model kinds register a ``(predicate, builder)`` pair, so this module
stays ORM-free and adapters plug in from outside (CONSTITUTION §2, §5).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

from pydantic import BaseModel

SchemaBuilder = Callable[[type], type[BaseModel]]


class SchemaRegistry:
    """Maps model classes to Pydantic schema classes via registered builders."""

    def __init__(self) -> None:
        self._builders: list[tuple[Callable[[type], bool], SchemaBuilder]] = []
        # Weak keys: a test that re-declares a model must not leak its schema.
        self._cache: WeakKeyDictionary[type, type[BaseModel]] = WeakKeyDictionary()

    def register(self, predicate: Callable[[type], bool], builder: SchemaBuilder) -> None:
        """Register ``builder`` for every model class where ``predicate`` is true."""
        self._builders.append((predicate, builder))

    def schema_for(self, model: type) -> type[BaseModel]:
        """Return the schema class for ``model``, building it at most once."""
        if issubclass(model, BaseModel):
            return model
        cached = self._cache.get(model)
        if cached is not None:
            return cached
        for predicate, builder in self._builders:
            if predicate(model):
                schema = builder(model)
                self._cache[model] = schema
                return schema
        msg = f"No schema builder registered for model {model.__name__!r}"
        raise TypeError(msg)

    def clear_cache(self) -> None:
        """Drop all built schemas (for test fixtures that mutate models)."""
        self._cache.clear()


schema_registry = SchemaRegistry()


def schema_for(model: type) -> type[BaseModel]:
    """Return the Pydantic schema class describing ``model``'s fields."""
    return schema_registry.schema_for(model)


def dump_instance(
    instance: object,
    *,
    exclude: set[str] | None = None,
    exclude_none: bool = False,
) -> dict[str, Any]:
    """Dump ``instance`` to a dict of its schema fields.

    Pydantic instances use ``model_dump``. Other instances have their schema fields
    read straight from ``__dict__``: no validation, and no lazy relationship or
    deferred-column loads (unloaded attributes dump as ``None``).
    """
    if isinstance(instance, BaseModel):
        return instance.model_dump(exclude=exclude, exclude_none=exclude_none)
    loaded = vars(instance)
    excluded = exclude or set()
    data = {
        name: loaded.get(name)
        for name in schema_for(type(instance)).model_fields
        if name not in excluded
    }
    if exclude_none:
        data = {k: v for k, v in data.items() if v is not None}
    return data
