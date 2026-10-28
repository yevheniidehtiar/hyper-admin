"""Unit tests for the ORM-free schema registry (``hyperadmin.core.schema``)."""

from __future__ import annotations

import gc
from typing import Any

import pytest
from pydantic import BaseModel, create_model
from sqlmodel import Field, SQLModel

from hyperadmin import core
from hyperadmin.core.schema import (
    SchemaRegistry,
    dump_instance,
    schema_for,
    schema_registry,
)


class _Hero(SQLModel, table=True):
    __tablename__ = "core_schema_hero"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    note: str | None = None


class _Plain:
    """Stand-in for a non-Pydantic (ORM-mapped) model."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


_PlainSchema = create_model("_PlainSchema", id=(int, 0), name=(str, ""), note=(str | None, None))


def _is_plain(model: type) -> bool:
    return issubclass(model, _Plain)


@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry()


def test_sqlmodel_model_is_its_own_schema(registry: SchemaRegistry) -> None:
    """
    Scenario: SQLModel models are unaffected
      Given a SQLModel table model
      When  schema_for is called
      Then  the model class itself is returned
    """
    assert registry.schema_for(_Hero) is _Hero
    assert schema_for(_Hero) is _Hero


def test_builder_runs_once_and_class_is_cached(registry: SchemaRegistry) -> None:
    """
    Scenario: builder result is cached per model class
      Given a registered builder whose predicate matches
      When  schema_for is called twice
      Then  the builder runs once and the same class is returned
    """
    calls: list[type] = []

    def builder(model: type) -> type[BaseModel]:
        calls.append(model)
        return _PlainSchema

    registry.register(_is_plain, builder)

    first = registry.schema_for(_Plain)
    second = registry.schema_for(_Plain)

    assert first is second is _PlainSchema
    assert calls == [_Plain]


def test_first_matching_builder_wins(registry: SchemaRegistry) -> None:
    """
    Scenario: the first matching builder is used
      Given two builders whose predicates both match
      When  schema_for is called
      Then  the first registered builder's schema is returned
    """
    other = create_model("Other", x=(int, 0))
    registry.register(lambda m: False, lambda m: other)
    registry.register(_is_plain, lambda m: _PlainSchema)
    registry.register(_is_plain, lambda m: other)

    assert registry.schema_for(_Plain) is _PlainSchema


def test_no_matching_builder_raises_type_error_naming_model(
    registry: SchemaRegistry,
) -> None:
    """
    Scenario: unknown model raises TypeError
      Given no matching builder
      When  schema_for is called
      Then  TypeError names the model
    """
    with pytest.raises(TypeError, match="_Plain"):
        registry.schema_for(_Plain)


def test_clear_cache_forces_rebuild(registry: SchemaRegistry) -> None:
    """
    Scenario: clear_cache drops built schemas
      Given a cached schema
      When  clear_cache is called and schema_for is called again
      Then  the builder runs a second time
    """
    calls: list[type] = []

    def builder(model: type) -> type[BaseModel]:
        calls.append(model)
        return _PlainSchema

    registry.register(_is_plain, builder)
    registry.schema_for(_Plain)
    registry.clear_cache()
    registry.schema_for(_Plain)

    assert len(calls) == 2


def test_cache_does_not_keep_model_classes_alive(registry: SchemaRegistry) -> None:
    """
    Scenario: re-declared models do not leak
      Given a schema cached for a throwaway model class
      When  the class is garbage collected
      Then  the cache no longer holds an entry for it
    """
    registry.register(_is_plain, lambda m: _PlainSchema)
    throwaway = type("Throwaway", (_Plain,), {})
    registry.schema_for(throwaway)
    assert len(registry._cache) == 1

    del throwaway
    gc.collect()

    assert len(registry._cache) == 0


def test_dump_instance_matches_model_dump_for_pydantic() -> None:
    """
    Scenario: Pydantic instances dump via model_dump
      Given a Pydantic instance
      When  dump_instance is called with exclude and exclude_none
      Then  it equals model_dump with the same arguments
    """
    hero = _Hero(id=1, name="Ada", note=None)

    assert dump_instance(hero, exclude={"id"}) == hero.model_dump(exclude={"id"})
    assert dump_instance(hero, exclude_none=True) == hero.model_dump(exclude_none=True)
    assert dump_instance(hero) == hero.model_dump()


def test_dump_instance_reads_schema_fields_without_lazy_loads() -> None:
    """
    Scenario: non-Pydantic instances dump their schema fields
      Given a non-Pydantic instance with a registered schema and a lazy attribute
      When  dump_instance is called
      Then  only schema fields are returned, read from __dict__, and unloaded ones are None
    """

    class Exploding(_Plain):
        @property
        def note(self) -> object:  # a lazy load would raise
            raise AssertionError("lazy load triggered")

    schema_registry.register(lambda m: m is Exploding, lambda m: _PlainSchema)
    try:
        obj = Exploding(id=7, name="x", unrelated=1)
        assert dump_instance(obj) == {"id": 7, "name": "x", "note": None}
    finally:
        schema_registry._builders.pop()
        schema_registry.clear_cache()


def test_dump_instance_honours_exclude_and_exclude_none() -> None:
    """
    Scenario: non-Pydantic dump supports exclude and exclude_none
      Given a non-Pydantic instance with a registered schema
      When  dump_instance is called with exclude and exclude_none
      Then  excluded and None-valued fields are dropped
    """
    schema_registry.register(lambda m: m is _Plain, lambda m: _PlainSchema)
    try:
        obj = _Plain(id=1, name="x", note=None)
        assert dump_instance(obj, exclude={"id"}) == {"name": "x", "note": None}
        assert dump_instance(obj, exclude_none=True) == {"id": 1, "name": "x"}
    finally:
        schema_registry._builders.pop()
        schema_registry.clear_cache()


def test_public_reexports_from_core() -> None:
    """
    Scenario: third-party adapters can import the seam from hyperadmin.core
      Given the hyperadmin.core package
      When  schema_for, SchemaRegistry and schema_registry are imported from it
      Then  they are the objects defined in hyperadmin.core.schema
    """
    assert core.schema_for is schema_for
    assert core.SchemaRegistry is SchemaRegistry
    assert core.schema_registry is schema_registry
