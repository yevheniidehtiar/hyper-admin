"""Search must not push free text through a column's TypeDecorator bind processor (#975)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import ForeignKey, String, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import StaticPool

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter

pytestmark = pytest.mark.anyio


class HexColor(TypeDecorator[str]):
    """Stores a ``#rrggbb`` string and rejects anything else when binding."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError(f"Expected a hex color, got {value}")
        return value


class _Base(DeclarativeBase):
    pass


class Label(_Base):
    __tablename__ = "search_td_label"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(HexColor(), default="#ffffff")


class Item(_Base):
    __tablename__ = "search_td_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(50))
    label_id: Mapped[int | None] = mapped_column(ForeignKey("search_td_label.id"))
    label: Mapped[Label | None] = relationship()


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_list_search_over_a_validating_column_type_does_not_raise(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: searching a model with a validating column type does not raise
      Given a Label whose color column rejects values that are not #rrggbb
      When  list() is called with search="a" over every inferred column
      Then  it returns the rows matching on name, with their total
      And   the pattern was not passed through the column type's bind processor
    """
    adapter = SQLAlchemyAdapter(model=Label, engine=engine)
    await adapter.create({"name": "alpha", "color": "#aabbcc"})
    await adapter.create({"name": "beta", "color": "#112233"})
    await adapter.create({"name": "zzz", "color": "#445566"})

    items, total = await adapter.list(search="a")

    assert sorted(item.name for item in items) == ["alpha", "beta"]
    assert total == 2


async def test_list_search_can_match_the_validated_column_itself(engine: AsyncEngine) -> None:
    """
    Scenario: the validated column is still searchable as text
      Given a Label with color "#aabbcc"
      When  list() searches "bbc"
      Then  the row is found through the color column
    """
    adapter = SQLAlchemyAdapter(model=Label, engine=engine)
    await adapter.create({"name": "one", "color": "#aabbcc"})
    await adapter.create({"name": "two", "color": "#112233"})

    items, total = await adapter.list(search="bbc", search_fields=["color"])

    assert [item.name for item in items] == ["one"]
    assert total == 1


async def test_choices_search_over_a_validating_column_type_does_not_raise(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: the relation picker's search is also safe
      Given Items pointing at Labels with a validating color column
      When  get_choices("label") is called with q="a"
      Then  it returns the matching Labels without raising
    """
    adapter = SQLAlchemyAdapter(model=Item, engine=engine)
    labels = SQLAlchemyAdapter(model=Label, engine=engine)
    await labels.create({"name": "alpha", "color": "#aabbcc"})
    await labels.create({"name": "zzz", "color": "#445566"})

    choices = await adapter.get_choices("label", q="a")

    assert [choice["label"] for choice in choices] == ["alpha"]


@pytest.mark.parametrize("adapter_cls", [SQLModelAdapter, SQLAlchemyAdapter])
async def test_both_adapters_search_without_validating_the_pattern(
    engine: AsyncEngine, adapter_cls: type
) -> None:
    """
    Scenario: the SQLModel adapter is protected the same way
      Given Labels with a validating color column
      When  either adapter lists with search="a" and resolves relation choices with q="a"
      Then  both succeed
    """
    labels = SQLAlchemyAdapter(model=Label, engine=engine)
    await labels.create({"name": "alpha", "color": "#aabbcc"})
    await labels.create({"name": "zzz", "color": "#445566"})

    items, total = await adapter_cls(model=Label, engine=engine).list(search="a")
    choices = await adapter_cls(model=Item, engine=engine).get_choices("label", q="a")

    assert (total, [item.name for item in items]) == (1, ["alpha"])
    assert [choice["label"] for choice in choices] == ["alpha"]
