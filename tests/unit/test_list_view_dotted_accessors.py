"""A dotted ``list_display`` accessor (``"customer.name"``) renders the related value.

v1.0 public API audit (st-v100-freeze-03), finding 7: the relation was loaded but
``_list_rows`` read ``getattr(item, "customer.name")``, so the cell stayed empty.
"""

from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

LIST_URL = "/admin/daorder"


class DaRegion(SQLModel, table=True):
    __tablename__ = "test_da_region"
    id: int | None = Field(default=None, primary_key=True)
    code: str


class DaCustomer(SQLModel, table=True):
    __tablename__ = "test_da_customer"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    password_hash: str = "pbkdf2$secret-hash"
    region_id: int | None = Field(default=None, foreign_key="test_da_region.id")

    region: Mapped[DaRegion | None] = Relationship()


class DaOrder(SQLModel, table=True):
    __tablename__ = "test_da_order"
    id: int | None = Field(default=None, primary_key=True)
    number: str
    customer_id: int | None = Field(default=None, foreign_key="test_da_customer.id")

    customer: Mapped[DaCustomer | None] = Relationship()


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


async def _seed_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        session.add(DaRegion(id=1, code="EU-WEST"))
        session.add(DaCustomer(id=1, name="Ada Lovelace", region_id=1))
        session.add(DaOrder(id=1, number="ORD-1", customer_id=1))
        session.add(DaOrder(id=2, number="ORD-2", customer_id=None))
        await session.commit()
    return engine


def _client(list_display: list[str]) -> TestClient:
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=anyio.run(_seed_engine),
        settings=HyperAdminSettings(create_tables=False),
    )
    options = AdminOptions(list_display=list_display)
    site.register(
        DaOrder,
        type("DaOrderAdmin", (ModelAdmin,), {"adapter_class": SQLModelAdapter, "options": options}),
    )
    admin.mount(path="/admin")
    return TestClient(app)


def _cells(response: Any, field: str) -> dict[int, Any]:
    return {row["_pk"]: row[field] for row in response.context["items"]}


def test_dotted_accessor_renders_the_related_value() -> None:
    """
    Scenario: a dotted accessor shows the related row's attribute
      Given an order admin with list_display ["number", "customer.name"]
      When  GET the order list
      Then  the customer.name cell of ORD-1 is "Ada Lovelace"
      And   the page shows the name
    """
    response = _client(["number", "customer.name"]).get(LIST_URL)

    assert response.status_code == 200
    assert _cells(response, "customer.name")[1] == "Ada Lovelace"
    assert "Ada Lovelace" in response.text


def test_dotted_accessor_past_the_loaded_relation_is_empty() -> None:
    """
    Scenario: a hop the list query did not load leaves the cell empty
      Given an order admin with list_display ["number", "customer.region.code"]
      And   the list query loads only the customer relation
      When  GET the order list
      Then  the page renders with an empty customer.region.code cell, not a 500
    """
    response = _client(["number", "customer.region.code"]).get(LIST_URL)

    assert response.status_code == 200
    assert _cells(response, "customer.region.code")[1] is None


def test_follow_accessor_stops_at_a_relation_the_query_did_not_load() -> None:
    """
    Scenario: an unloaded relation is never lazy-loaded on a closed session
      Given a customer read in a session that is now closed, without its region
      When  the accessor "customer.region.code" is followed from an order holding it
      Then  the result is None and no DetachedInstanceError is raised
    """
    from types import SimpleNamespace

    from hyperadmin.views.dynamic.list_view import _follow_accessor

    async def _detached_customer() -> DaCustomer:
        engine = await _seed_engine()
        async with AsyncSession(engine) as session:
            customer = await session.get(DaCustomer, 1)
        assert customer is not None
        return customer

    order = SimpleNamespace(customer=anyio.run(_detached_customer))

    assert _follow_accessor(order, "customer.region.code") is None
    assert _follow_accessor(order, "customer.name") == "Ada Lovelace"


def test_dotted_accessor_is_empty_when_the_relation_is_unset() -> None:
    """
    Scenario: a missing related row leaves the cell empty
      Given an order without a customer and list_display ["number", "customer.name"]
      When  GET the order list
      Then  the customer.name cell of that order is empty, not an error
    """
    response = _client(["number", "customer.name"]).get(LIST_URL)

    assert response.status_code == 200
    assert _cells(response, "customer.name")[2] in (None, "")


def test_dotted_accessor_never_shows_a_sensitive_related_field() -> None:
    """
    Scenario: a dotted accessor to a sensitive related field shows nothing
      Given an order admin with list_display ["number", "customer.password_hash"]
      When  GET the order list
      Then  the cell is empty
      And   the hash never appears in the page
    """
    response = _client(["number", "customer.password_hash"]).get(LIST_URL)

    assert response.status_code == 200
    assert _cells(response, "customer.password_hash")[1] in (None, "")
    assert "secret-hash" not in response.text
