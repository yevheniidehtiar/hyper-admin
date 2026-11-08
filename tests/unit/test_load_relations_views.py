"""The list and detail pages load only the relations they need (SDD adapter-query-performance A1)."""

from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class LvCategory(SQLModel, table=True):
    __tablename__ = "test_lv_category"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class LvVendor(SQLModel, table=True):
    __tablename__ = "test_lv_vendor"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class LvProduct(SQLModel, table=True):
    __tablename__ = "test_lv_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    category_id: int | None = Field(default=None, foreign_key="test_lv_category.id")
    vendor_id: int | None = Field(default=None, foreign_key="test_lv_vendor.id")

    category: Mapped[LvCategory | None] = Relationship()
    vendor: Mapped[LvVendor | None] = Relationship()


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _client(**options: Any) -> tuple[TestClient, list[str]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine) as session:
            session.add(LvCategory(id=1, name="Tools"))
            session.add(LvVendor(id=1, name="Acme"))
            session.add(LvProduct(id=1, name="P1", category_id=1, vendor_id=1))
            await session.commit()

    anyio.run(setup)

    statements: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _capture(conn: Any, cursor: Any, statement: str, *rest: Any) -> None:
        statements.append(statement)

    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(
        LvProduct,
        type(
            "LvProductAdmin",
            (ModelAdmin,),
            {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app), statements


def _queried_tables(statements: list[str]) -> set[str]:
    """Tables loaded by a ``selectinload`` (``... WHERE id IN (...)``), not by filter choices."""
    tables = ("test_lv_category", "test_lv_vendor")
    return {t for t in tables if any(f"FROM {t}" in s and " IN (" in s for s in statements)}


def test_list_page_loads_no_relation_by_default() -> None:
    """
    Scenario: the list page issues no relation SELECTs by default
      Given a product admin whose columns name no relation
      When  the list page is rendered
      Then  no relation table is queried
    """
    client, statements = _client(list_display=["id", "name"])

    assert client.get("/admin/lvproduct").status_code == 200
    assert _queried_tables(statements) == set()


def test_list_page_loads_the_relations_named_in_list_display() -> None:
    """
    Scenario: a relation in the columns is loaded on the list page
      Given list_display ["id", "category"]
      When  the list page is rendered
      Then  category is queried
      And   vendor is not
    """
    client, statements = _client(list_display=["id", "category"])

    assert client.get("/admin/lvproduct").status_code == 200
    assert _queried_tables(statements) == {"test_lv_category"}


def test_list_select_related_loads_the_named_relation() -> None:
    """
    Scenario: list_select_related loads a relation the columns do not name
      Given list_select_related ["vendor"] and auto_select_related off
      When  the list page is rendered
      Then  vendor is queried
      And   category is not
    """
    client, statements = _client(
        list_display=["id", "name"], list_select_related=["vendor"], auto_select_related=False
    )

    assert client.get("/admin/lvproduct").status_code == 200
    assert _queried_tables(statements) == {"test_lv_vendor"}


def test_detail_select_related_limits_the_detail_page_relations() -> None:
    """
    Scenario: detail_select_related limits what the detail page loads
      Given detail_select_related ["category"]
      When  the detail page is rendered
      Then  category is queried
      And   vendor is not
    """
    client, statements = _client(detail_select_related=["category"])

    assert client.get("/admin/lvproduct/1").status_code == 200
    assert _queried_tables(statements) == {"test_lv_category"}
