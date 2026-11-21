"""``HyperAdminSettings.items_per_page`` is the list page size without ``?page_size=``.

v1.0 public API audit (st-v100-freeze-03), finding 1: the setting was public but never read.
"""

from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

ROWS = 130
LIST_URL = "/admin/ippitem"


class IppItem(SQLModel, table=True):
    __tablename__ = "test_ipp_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str


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
        session.add_all(IppItem(id=i, name=f"item {i:03d}") for i in range(1, ROWS + 1))
        await session.commit()
    return engine


def _client(**settings: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=anyio.run(_seed_engine),
        settings=HyperAdminSettings(create_tables=False, **settings),
    )
    site.register(IppItem, type("IppItemAdmin", (ModelAdmin,), {"adapter_class": SQLModelAdapter}))
    admin.mount(path="/admin")
    return TestClient(app)


def _shown(response: Any) -> tuple[int, int]:
    pagination = response.context["pagination"]
    return len(response.context["items"]), pagination["page_size"]


def test_list_page_uses_items_per_page_without_page_size() -> None:
    """
    Scenario: the setting sets the default page size
      Given HyperAdminSettings(items_per_page=25) and 130 rows
      When  GET the list without a page_size parameter
      Then  25 rows are listed and the pager reports a page size of 25
    """
    response = _client(items_per_page=25).get(LIST_URL)

    assert response.status_code == 200
    assert _shown(response) == (25, 25)


def test_page_size_query_parameter_overrides_items_per_page() -> None:
    """
    Scenario: an explicit page_size wins over the setting
      Given HyperAdminSettings(items_per_page=25)
      When  GET the list with page_size=50
      Then  50 rows are listed
    """
    response = _client(items_per_page=25).get(LIST_URL, params={"page_size": 50})

    assert _shown(response) == (50, 50)


def test_items_per_page_above_the_maximum_is_capped_at_100() -> None:
    """
    Scenario: a setting above the list maximum is capped
      Given HyperAdminSettings(items_per_page=500) and 130 rows
      When  GET the list without a page_size parameter
      Then  100 rows are listed, the most one list page shows
    """
    response = _client(items_per_page=500).get(LIST_URL)

    assert _shown(response) == (100, 100)


def test_default_items_per_page_keeps_ten_rows() -> None:
    """
    Scenario: without the setting the page size stays 10
      Given default HyperAdminSettings
      When  GET the list without a page_size parameter
      Then  10 rows are listed, as before the setting was read
    """
    response = _client().get(LIST_URL)

    assert _shown(response) == (10, 10)
