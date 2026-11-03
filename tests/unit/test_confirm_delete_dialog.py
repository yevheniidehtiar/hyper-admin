"""Red icon delete and the shared confirm dialog (st-v059-list-03).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Delete (list-03)"). Delete
buttons on the list, detail and edit pages are triggers for one shared
``components/confirm_delete_dialog.html``; ``static/js/confirm_delete.js``
sends the DELETE with ``htmx.ajax`` from inside ``<body hx-headers>``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import hyperadmin
from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

SCRIPT = Path(hyperadmin.__file__).parent / "static" / "js" / "confirm_delete.js"


class DialogOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    number: str = "ORD-1"

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
            session.add(DialogOrder(id=42, number="ORD-1042"))
            await session.commit()

    anyio.run(setup)
    return eng


def _client(engine: Any, **options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(DialogOrder, _Admin, options=AdminOptions(**options))
    admin.mount(path="/admin")
    return TestClient(app)


def _trigger(html: str, testid: str) -> str:
    match = re.search(
        rf'<button[^>]*data-testid="{testid}"[^>]*>',
        html,
        re.DOTALL,
    )
    assert match, f"no {testid}"
    return match.group(0)


def test_the_list_renders_one_shared_alertdialog(engine) -> None:
    """
    Scenario: delete asks for confirmation in a dialog
      Given alice may delete orders
      When  the order list renders
      Then  exactly one alertdialog (dialog-confirm-delete) is on the page
      And   it is labelled by its "Delete {name}?" title, described by "This cannot be undone."
      And   Cancel comes first with the initial focus, then a solid danger Delete
      And   no native hx-confirm prompt is left on the page
    """
    html = _client(engine).get("/admin/dialogorder").text

    assert html.count('data-testid="dialog-confirm-delete"') == 1
    dialog = html[html.index('<dialog class="ha-dialog ha-confirm-delete"') :]
    dialog = dialog[: dialog.index("</dialog>")]
    assert 'role="alertdialog"' in dialog
    assert 'aria-labelledby="ha-confirm-delete-title"' in dialog
    assert 'aria-describedby="ha-confirm-delete-desc"' in dialog
    assert 'data-title-template="Delete {name}?"' in dialog
    assert "This cannot be undone." in dialog
    assert dialog.index("data-ha-confirm-cancel autofocus") < dialog.index(
        'class="ha-btn ha-btn--danger" data-ha-confirm-ok'
    )
    assert html.count("/static/js/confirm_delete.js") == 1
    assert "hx-confirm" not in html


def test_the_row_delete_is_a_labelled_icon_trigger(engine) -> None:
    """
    Scenario: the row delete is a red ghost icon button
      Given alice may delete orders
      When  the order list renders
      Then  row-delete-btn is an icon button labelled "Delete ORD-1042" with a tooltip
      And   it points the dialog at DELETE /admin/dialogorder/42
    """
    html = _client(engine).get("/admin/dialogorder").text

    button = _trigger(html, "row-delete-btn")
    assert 'class="ha-btn ha-btn--icon ha-btn--ghost ha-btn--danger-icon"' in button
    assert 'aria-label="Delete ORD-1042"' in button
    assert 'data-ha-label="ORD-1042"' in button
    assert re.search(r'data-ha-confirm-delete="[^"]+/admin/dialogorder/42"', button)
    assert '<span class="ha-tooltip" aria-hidden="true">Delete</span>' in html


def test_users_who_may_not_delete_get_no_delete_icon(engine) -> None:
    """
    Scenario: users without delete_order see no delete icon
      Given deletes are disabled for the model
      When  the order list renders
      Then  no row-delete-btn and no actions column are rendered
    """
    html = _client(engine, can_delete=False).get("/admin/dialogorder").text

    assert "row-delete-btn" not in html
    assert "ha-col-end" not in html


def test_detail_and_edit_deletes_use_the_same_dialog(engine) -> None:
    """
    Scenario: the detail and edit pages delete through the shared dialog
      Given alice may delete orders
      When  she opens the detail page and the edit page of order 42
      Then  detail-delete-btn and form-delete-btn are dialog triggers for order 42
      And   each page carries the dialog once
    """
    client = _client(engine)

    for path, testid in (
        ("/admin/dialogorder/42", "detail-delete-btn"),
        ("/admin/dialogorder/42/edit", "form-delete-btn"),
    ):
        html = client.get(path).text
        button = _trigger(html, testid)
        assert 'data-ha-label="ORD-1042"' in button
        assert re.search(r'data-ha-confirm-delete="[^"]+/admin/dialogorder/42"', button)
        assert 'type="button"' in button
        assert html.count('data-testid="dialog-confirm-delete"') == 1


def test_the_script_sends_the_delete_through_htmx_with_the_csrf_header() -> None:
    """
    Scenario: confirming sends the DELETE with the page's CSRF header
      Given the shared dialog script
      When  it confirms a delete
      Then  it calls htmx.ajax("DELETE", url) sourced from the dialog inside <body hx-headers>
      And   closing returns focus to the trigger
    """
    script = SCRIPT.read_text()

    assert 'window.htmx.ajax("DELETE", state.url, { source: box, swap: "none" })' in script
    assert "opener.focus()" in script
    assert '"ha-confirm-delete"' in script
