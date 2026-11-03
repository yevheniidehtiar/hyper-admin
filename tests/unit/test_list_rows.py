"""Clickable list rows and the record-page Edit / View / Delete (st-v059-list-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Rows (list-02)"). The title
cell holds the row link (``row-link``) to the edit page for editors and to the
detail page for read-only users; the detail page offers Edit and the edit page
offers View, each gated by the page option plus the model-level permission.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic import DynamicModelView


class RowOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    number: str = "ORD-1"
    status: str | None = "new"

    def __str__(self) -> str:
        return self.number


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(eng, expire_on_commit=False) as session:
            session.add(RowOrder(id=42, number="ORD-1042", status="paid"))
            await session.commit()

    anyio.run(setup)
    return eng


def _client(engine: Any, **options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(RowOrder, _Admin, options=AdminOptions(**options))
    admin.mount(path="/admin")
    return TestClient(app)


def _row_link(html: str) -> str:
    match = re.search(
        r'<a class="ha-row-link[^"]*" href="([^"]+)"[^>]*data-testid="row-link"', html
    )
    assert match, "no row-link"
    return match.group(1)


# ---------------------------------------------------------------------------
# List rows
# ---------------------------------------------------------------------------


def test_the_title_cell_links_editors_to_the_edit_page(engine) -> None:
    """
    Scenario: clicking a row opens the edit page for an editor
      Given an Order list the user may change
      When  the list renders
      Then  the first non-editable column is a <th scope="row"> holding row-link
      And   row-link goes to /admin/roworder/42/edit
      And   the old View and Edit buttons are gone
    """
    client = _client(engine, list_display=["number", "status"])

    html = client.get("/admin/roworder").text

    assert re.search(
        r'<th class="ha-table-cell ha-table-title" scope="row" data-label="Number">', html
    )
    assert _row_link(html).endswith("/admin/roworder/42/edit")
    assert 'class="ha-table-row ha-table-row--link"' in html
    assert "row-view-link" not in html
    assert "row-edit-link" not in html


def test_the_title_cell_links_read_only_users_to_the_detail_page(engine) -> None:
    """
    Scenario: clicking a row opens the detail page for a read-only user
      Given edits are disabled for Order
      When  the list renders
      Then  row-link goes to the detail page /admin/roworder/42
    """
    client = _client(engine, list_display=["number", "status"], can_edit=False)

    html = client.get("/admin/roworder").text

    assert _row_link(html).endswith("/admin/roworder/42")


def test_rows_without_a_target_render_plain_text(engine) -> None:
    """
    Scenario: rows without edit or detail are not interactive
      Given AdminOptions(can_edit=False, can_detail=False, can_delete=False)
      When  the list renders
      Then  the title cell is plain text, no row-link, no actions column
    """
    client = _client(
        engine,
        list_display=["number", "status"],
        can_edit=False,
        can_detail=False,
        can_delete=False,
    )

    html = client.get("/admin/roworder").text

    assert 'data-testid="row-link"' not in html
    assert "ha-table-row--link" not in html
    assert ">ORD-1042</th>" in html
    assert "ha-col-end" not in html


def test_the_title_link_skips_inline_editable_columns(engine) -> None:
    """
    Scenario: the title link goes on the first non-editable column
      Given list_editable=["number"] and columns number, status
      When  the list renders
      Then  number stays an inline-edit cell and status holds row-link
    """
    client = _client(engine, list_display=["number", "status"], list_editable=["number"])

    html = client.get("/admin/roworder").text

    assert 'data-testid="cell-edit-number-42"' in html
    assert re.search(r'scope="row" data-label="Status"><a class="ha-row-link"', html)


def test_all_editable_rows_get_a_chevron_open_link(engine) -> None:
    """
    Scenario: every column editable gets a chevron open link
      Given list_editable covers every displayed column
      When  the list renders
      Then  an end cell holds row-link labelled "Open ORD-1042" with a mirrored chevron
    """
    client = _client(engine, list_display=["number", "status"], list_editable=["number", "status"])

    html = client.get("/admin/roworder").text

    assert 'scope="row"' not in html
    assert re.search(
        r'<a class="ha-row-link ha-row-open" href="[^"]+/admin/roworder/42/edit" '
        r'data-testid="row-link"\s+aria-label="Open ORD-1042">',
        html,
    )
    assert "ha-icon--mirror" in html


def test_a_null_title_keeps_an_accessible_link_name(engine) -> None:
    """
    Scenario: a title cell with no value still names the record
      Given the title column is empty for order 42
      When  the list renders
      Then  the row link shows a dash and a screen-reader label "ORD-1042"
    """

    async def blank() -> None:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            order = await session.get(RowOrder, 42)
            assert order is not None
            order.status = None
            session.add(order)
            await session.commit()

    anyio.run(blank)
    client = _client(engine, list_display=["status", "number"])

    html = client.get("/admin/roworder").text

    assert '<span class="ha-sr-only">ORD-1042</span></a>' in html


def test_list_rows_carry_the_display_label(engine) -> None:
    """
    Scenario: each row carries the record's display name
      Given an Order whose __str__ is its number
      When  the list rows are built
      Then  the row has _label "ORD-1042"
    """
    view = DynamicModelView(
        adapter=SQLModelAdapter(RowOrder, engine),
        options=AdminOptions(),
        templates=MagicMock(),
        app_label="test",
    )

    rows = view._list_rows([RowOrder(id=42, number="ORD-1042")], set())

    assert rows[0]["_label"] == "ORD-1042"


# ---------------------------------------------------------------------------
# Detail and edit pages
# ---------------------------------------------------------------------------


def test_the_detail_page_offers_edit_and_delete(engine) -> None:
    """
    Scenario: the detail page offers Edit to editors
      Given the user may change and delete orders
      When  the user opens /admin/roworder/42
      Then  an "Edit" link (detail-edit-link) leads to /admin/roworder/42/edit
      And   a Delete button (detail-delete-btn) is shown
    """
    client = _client(engine)

    html = client.get("/admin/roworder/42").text

    match = re.search(r'href="([^"]+)" class="[^"]*" data-testid="detail-edit-link"', html)
    assert match
    assert match.group(1).endswith("/admin/roworder/42/edit")
    assert 'data-testid="detail-delete-btn"' in html


def test_the_detail_page_hides_edit_and_delete_when_disabled(engine) -> None:
    """
    Scenario: the detail page hides Edit and Delete when the model disables them
      Given AdminOptions(can_edit=False, can_delete=False)
      When  the user opens the detail page
      Then  neither detail-edit-link nor detail-delete-btn is rendered
    """
    client = _client(engine, can_edit=False, can_delete=False)

    html = client.get("/admin/roworder/42").text

    assert "detail-edit-link" not in html
    assert "detail-delete-btn" not in html


def test_the_edit_page_offers_view_and_delete(engine) -> None:
    """
    Scenario: the edit page offers View and Delete
      Given the detail page is enabled and the user may delete
      When  the user opens /admin/roworder/42/edit
      Then  a "View" link (form-view-link) leads to /admin/roworder/42
      And   a Delete button (form-delete-btn) is shown
    """
    client = _client(engine)

    html = client.get("/admin/roworder/42/edit").text

    match = re.search(r'href="([^"]+)" class="[^"]*" data-testid="form-view-link"', html)
    assert match
    assert match.group(1).endswith("/admin/roworder/42")
    assert 'data-testid="form-delete-btn"' in html


def test_the_edit_page_hides_view_without_a_detail_page(engine) -> None:
    """
    Scenario: the edit page has no View link when the detail page is off
      Given AdminOptions(can_detail=False, can_delete=False)
      When  the user opens the edit page
      Then  neither form-view-link nor form-delete-btn is rendered
    """
    client = _client(engine, can_detail=False, can_delete=False)

    html = client.get("/admin/roworder/42/edit").text

    assert "form-view-link" not in html
    assert "form-delete-btn" not in html


class _GrantedChecker:
    """Permission checker granting a fixed set of codenames."""

    def __init__(self, *granted: str) -> None:
        self.granted = set(granted)

    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in self.granted


def _view(checker: Any, **options: Any) -> DynamicModelView:
    return DynamicModelView(
        adapter=SQLModelAdapter(RowOrder, object()),
        options=AdminOptions(**options),
        templates=MagicMock(),
        app_label="test",
        permission_checker=checker,
    )


def _request() -> Request:
    request = MagicMock(spec=Request)
    request.headers = {}
    request.state = SimpleNamespace(user=SimpleNamespace(id=1))
    return request


async def test_a_read_only_user_gets_no_edit_or_delete(anyio_backend) -> None:
    """
    Scenario: the record pages follow the user's model permissions
      Given bob holds view_roworder only
      When  the record-page actions are computed
      Then  bob may view but not edit or delete
    """
    view = _view(_GrantedChecker("view_roworder"))

    actions = await view._record_actions(_request())

    assert actions == {"user_can_edit": False, "user_can_view": True, "user_can_delete": False}


async def test_an_editor_gets_edit_view_and_delete(anyio_backend) -> None:
    """
    Scenario: an editor gets every record-page action
      Given alice holds view, change and delete on roworder
      When  the record-page actions are computed
      Then  Edit, View and Delete are all offered
    """
    view = _view(_GrantedChecker("view_roworder", "change_roworder", "delete_roworder"))

    actions = await view._record_actions(_request())

    assert actions == {"user_can_edit": True, "user_can_view": True, "user_can_delete": True}


async def test_page_options_win_over_permissions(anyio_backend) -> None:
    """
    Scenario: a disabled page is never offered, whatever the permissions
      Given AdminOptions(can_edit=False, can_detail=False, can_delete=False)
      And   alice holds every roworder permission
      When  the record-page actions are computed
      Then  nothing is offered and no permission is checked
    """
    checker = MagicMock()
    view = _view(checker, can_edit=False, can_detail=False, can_delete=False)

    actions = await view._record_actions(_request())

    assert actions == {"user_can_edit": False, "user_can_view": False, "user_can_delete": False}
    checker.has_permission.assert_not_called()
