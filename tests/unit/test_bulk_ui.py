"""Rendering tests for the list-view bulk UI (H3, v0.5.5).

Mirrors the scenarios in
``.meta/epics/epic-v055-bulk-actions/stories/feattemplates-add-checkbox-column-and-bulk-toolbar.md``:
the checkbox column and toolbar appear only when a ``bulk=True`` action exists,
and the result grid renders one row per outcome with a "Retry failures" form.
"""

from __future__ import annotations

import re

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

_fail_ids: set[int] = set()


class BulkUiProduct(SQLModel, table=True):
    __tablename__ = "test_bulk_ui_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class PlainProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Publish")
    async def publish(self, request: Request, item_id: int) -> None:
        return None


class BulkProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Archive", bulk=True)
    async def archive(self, request: Request, item_id: int, *, params=None) -> None:
        if item_id in _fail_ids:
            raise RuntimeError("x")

    @action(label="Archive overdue", bulk=True, requires_selection=False)
    async def archive_overdue(self, request: Request, item_id: int, *, params=None) -> None:
        return None

    @action(label="Publish")
    async def publish(self, request: Request, item_id: int) -> None:
        return None


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    _fail_ids.clear()
    yield
    site._registry = {}


def _client(admin_class: type[ModelAdmin]) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for name in ("alpha", "beta", "gamma"):
                session.add(BulkUiProduct(name=name))
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(BulkUiProduct, admin_class)
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_view_without_bulk_actions_hides_the_checkbox_column():
    """
    Scenario: list view without bulk actions hides the checkbox column
      Given a ModelAdmin with no @action(bulk=True)
      When  the user opens the list view
      Then  the rendered table has no element with data-testid="bulk-checkbox"
    """
    # Given
    client = _client(PlainProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/")

    # Then
    assert response.status_code == 200
    assert 'data-testid="list-row"' in response.text
    assert 'data-testid="bulk-checkbox"' not in response.text
    assert 'data-testid="bulk-select-all"' not in response.text
    assert 'data-testid="bulk-action-select"' not in response.text


def test_list_view_with_a_bulk_action_renders_the_toolbar():
    """
    Scenario: list view with at least one bulk action renders the toolbar
      Given a ModelAdmin with @action(label="Archive", bulk=True)
      When  the user opens the list view
      Then  the toolbar shows a bulk-action-select containing option "Archive"
      And   each row has data-testid="bulk-checkbox"
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/")

    # Then
    html = response.text
    assert response.status_code == 200
    select = re.search(r'<select[^>]*data-testid="bulk-action-select".*?</select>', html, re.DOTALL)
    assert select is not None
    options = re.findall(r"<option[^>]*>([^<]*)</option>", select.group(0))
    # Only bulk actions are offered; the single-record "Publish" action is not.
    assert options == ["Archive", "Archive overdue"]
    assert 'data-url="http://testserver/admin/bulkuiproduct/actions/archive/bulk"' in html
    assert 'data-requires-selection="true"' in html
    assert 'data-requires-selection="false"' in html
    assert html.count('data-testid="list-row"') == 3
    assert html.count('data-testid="bulk-checkbox"') == 3
    checkboxes = re.findall(r'<input[^>]*data-testid="bulk-checkbox"[^>]*>', html)
    assert all('form="bulk-action-form"' in box for box in checkboxes)
    assert sorted(re.search(r'value="(\d+)"', box).group(1) for box in checkboxes) == [
        "1",
        "2",
        "3",
    ]
    assert 'data-testid="bulk-run-btn"' in html
    assert 'data-testid="bulk-select-all"' in html


def test_htmx_list_partial_keeps_the_checkbox_column():
    """
    Scenario: paging or sorting through htmx keeps the checkbox column
      Given a ModelAdmin with a bulk action
      When  the list table is re-fetched as an htmx partial
      Then  each row still has data-testid="bulk-checkbox"
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/", headers={"HX-Request": "true"})

    # Then
    assert response.text.count('data-testid="bulk-checkbox"') == 3
    assert 'data-testid="bulk-toolbar"' in response.text


def test_result_page_renders_a_row_per_outcome_with_a_retry_form():
    """
    Scenario: result page renders a row per outcome
      Given run_bulk_action returns ok for id 1 and failed for id 2
      When  the result template renders
      Then  the page has two bulk-result-row entries
      And   the "Retry failures" form targets the bulk endpoint with ids=[2]
    """
    # Given
    client = _client(BulkProductAdmin)
    _fail_ids.add(2)

    # When
    response = client.post(
        "/admin/bulkuiproduct/actions/archive/bulk",
        data={"ids": ["1", "2"]},
        headers={"HX-Request": "true"},
    )

    # Then
    html = response.text
    assert response.status_code == 200
    assert html.count('data-testid="bulk-result-row"') == 2
    retry = re.search(r'<form[^>]*data-testid="bulk-retry-form".*?</form>', html, re.DOTALL)
    assert retry is not None
    assert 'hx-post="http://testserver/admin/bulkuiproduct/actions/archive/bulk"' in retry.group(0)
    assert 'hx-target="#bulk-result-region"' in retry.group(0)
    assert re.findall(r'name="ids" value="([^"]*)"', retry.group(0)) == ["2"]
    assert 'data-testid="bulk-retry-link"' in retry.group(0)


def test_result_page_omits_retry_when_every_row_succeeds():
    """
    Scenario: result page without failures has no "Retry failures" link
      Given every selected row succeeds
      When  the result template renders
      Then  no bulk-retry-link is rendered
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.post("/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ["1", "2"]})

    # Then
    assert response.text.count('data-testid="bulk-result-row"') == 2
    assert 'data-testid="bulk-retry-link"' not in response.text
