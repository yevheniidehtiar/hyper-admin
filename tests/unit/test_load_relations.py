"""Configurable relation loading on the list and detail paths (SDD adapter-query-performance A1)."""

from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.relation_loading import resolve_list_relations


class LrCategory(SQLModel, table=True):
    __tablename__ = "test_lr_category"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class LrVendor(SQLModel, table=True):
    __tablename__ = "test_lr_vendor"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class LrProduct(SQLModel, table=True):
    __tablename__ = "test_lr_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    category_id: int | None = Field(default=None, foreign_key="test_lr_category.id")
    vendor_id: int | None = Field(default=None, foreign_key="test_lr_vendor.id")

    category: Mapped[LrCategory | None] = Relationship()
    vendor: Mapped[LrVendor | None] = Relationship()


@pytest.fixture
async def engine() -> AsyncEngine:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(eng) as session:
        session.add(LrCategory(id=1, name="Tools"))
        session.add(LrVendor(id=1, name="Acme"))
        for i in range(1, 4):
            session.add(LrProduct(id=i, name=f"P{i}", category_id=1, vendor_id=1))
        await session.commit()
    return eng


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_cls(request: pytest.FixtureRequest) -> type[SQLModelAdapter] | type[SQLAlchemyAdapter]:
    return request.param


def _record_selects(engine: AsyncEngine) -> list[str]:
    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _capture(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    return statements


def _loaded(item: Any, name: str) -> bool:
    return name in item.__dict__


@pytest.mark.anyio
async def test_list_without_load_relations_loads_no_relation(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: list with default options issues no relation SELECTs
      Given a product with two relations
      When  list() is called without load_relations
      Then  exactly one SELECT against product runs
      And   no relation is loaded
    """
    statements = _record_selects(engine)

    items, total = await adapter_cls(LrProduct, engine).list()

    assert total == 3
    assert len([s for s in statements if "FROM test_lr_product" in s and "count" not in s]) == 1
    assert not any("FROM test_lr_category" in s or "FROM test_lr_vendor" in s for s in statements)
    assert not any(_loaded(i, "category") or _loaded(i, "vendor") for i in items)


@pytest.mark.anyio
async def test_list_loads_only_the_named_relations(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: load_relations loads exactly the named relations
      Given load_relations=["category"]
      When  list() is called
      Then  category is loaded on every row
      And   vendor is not
    """
    items, _ = await adapter_cls(LrProduct, engine).list(load_relations=["category"])

    assert all(_loaded(i, "category") for i in items)
    assert not any(_loaded(i, "vendor") for i in items)


@pytest.mark.anyio
async def test_list_with_empty_load_relations_loads_nothing(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: an empty load_relations is the explicit form of loading nothing
      Given load_relations=[]
      When  list() is called
      Then  no relation is loaded
    """
    items, _ = await adapter_cls(LrProduct, engine).list(load_relations=[])

    assert not any(_loaded(i, "category") for i in items)


@pytest.mark.anyio
async def test_list_rejects_an_unknown_relation(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: an unknown relation name is rejected
      Given load_relations=["nope"]
      When  list() is called
      Then  ValueError names the relation
    """
    with pytest.raises(ValueError, match="nope"):
        await adapter_cls(LrProduct, engine).list(load_relations=["nope"])


@pytest.mark.anyio
async def test_get_loads_the_named_relations_only(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: get with explicit load_relations loads only those
      Given load_relations=["vendor"]
      When  get(1) is called
      Then  vendor is loaded
      And   category is not
    """
    item = await adapter_cls(LrProduct, engine).get(1, load_relations=["vendor"])

    assert _loaded(item, "vendor")
    assert not _loaded(item, "category")


@pytest.mark.anyio
async def test_get_with_empty_load_relations_loads_nothing(
    engine: AsyncEngine, adapter_cls: type[SQLModelAdapter]
) -> None:
    """
    Scenario: get with load_relations=[] loads no relation
      Given load_relations=[]
      When  get(1) is called
      Then  no relation is loaded
    """
    item = await adapter_cls(LrProduct, engine).get(1, load_relations=[])

    assert not _loaded(item, "category")
    assert not _loaded(item, "vendor")


@pytest.mark.anyio
async def test_sqlmodel_get_still_loads_every_relation_by_default(engine: AsyncEngine) -> None:
    """
    Scenario: detail view keeps auto-detect (backward compatible)
      Given detail_select_related is unset
      When  SQLModelAdapter.get(1) is called without load_relations
      Then  every relation is loaded
    """
    item = await SQLModelAdapter(LrProduct, engine).get(1)

    assert _loaded(item, "category")
    assert _loaded(item, "vendor")


def test_options_defaults_keep_detail_auto_and_derive_list_relations() -> None:
    """
    Scenario: relation loading options default to the SDD values
      Given AdminOptions()
      Then  list_select_related and detail_select_related are None
      And   auto_select_related is True
    """
    options = AdminOptions()

    assert options.list_select_related is None
    assert options.detail_select_related is None
    assert options.auto_select_related is True


RELATIONS = {"category", "vendor"}


def test_default_list_resolves_to_no_relations() -> None:
    """
    Scenario: no column_list relations means nothing is loaded
      Given a column_list of plain columns
      When  the list relations are resolved
      Then  the result is empty
    """
    assert resolve_list_relations(None, ["id", "name"], RELATIONS, auto=True) == []


def test_relation_accessor_in_column_list_is_derived() -> None:
    """
    Scenario: a relation accessor in column_list loads that relation
      Given column_list ["name", "category.name", "vendor"]
      When  the list relations are resolved with auto on
      Then  category and vendor are loaded, once each, in column order
    """
    columns = ["name", "category.name", "vendor", "category.id"]

    assert resolve_list_relations(None, columns, RELATIONS, auto=True) == ["category", "vendor"]


def test_auto_off_ignores_column_list() -> None:
    """
    Scenario: auto_select_related=False opts out of the derivation
      Given column_list ["category.name"] and auto off
      When  the list relations are resolved
      Then  nothing is loaded
    """
    assert resolve_list_relations(None, ["category.name"], RELATIONS, auto=False) == []


def test_explicit_list_select_related_is_added_to_the_derived_relations() -> None:
    """
    Scenario: list_select_related adds to the derived relations
      Given list_select_related ["vendor"] and column_list ["category.name"]
      When  the list relations are resolved with auto on
      Then  vendor and category are both loaded
    """
    assert resolve_list_relations(["vendor"], ["category.name"], RELATIONS, auto=True) == [
        "vendor",
        "category",
    ]


def test_unknown_column_prefix_is_not_a_relation() -> None:
    """
    Scenario: a dotted entry that is not a relation is ignored
      Given column_list ["other.name"]
      When  the list relations are resolved
      Then  nothing is loaded
    """
    assert resolve_list_relations(None, ["other.name"], RELATIONS, auto=True) == []
