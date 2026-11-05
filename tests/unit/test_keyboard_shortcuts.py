"""List keyboard navigation and the shortcuts overlay (st-v059-kbd-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Keyboard (kbd-02)"). Every page
built on ``_base.html`` renders ``components/shortcuts_overlay.html`` once;
``static/js/shortcuts.js`` fills it from ``haShortcuts.list()`` and registers the
list keys. Browser behaviour is covered by ``tests/e2e/test_keyboard_navigation.py``.
"""

from __future__ import annotations

import json
import re
from html import unescape
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
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

SCRIPT = Path(hyperadmin.__file__).parent / "static" / "js" / "shortcuts.js"


class KeysOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    number: str = "ORD-1"


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client() -> TestClient:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(eng, expire_on_commit=False) as session:
            session.add(KeysOrder(id=1, number="ORD-1"))
            await session.commit()

    anyio.run(setup)
    app = FastAPI()
    admin = Admin(app=app, engine=eng, settings=HyperAdminSettings(create_tables=False))
    site.register(KeysOrder, _Admin)
    admin.mount(path="/admin")
    return TestClient(app)


def _overlay(html: str) -> str:
    start = html.index('<dialog id="ha-shortcuts"')
    return html[start : html.index("</dialog>", start)]


@pytest.mark.parametrize("path", ["/admin/", "/admin/keysorder", "/admin/keysorder/1/edit"])
def test_every_page_renders_the_overlay_once(client: Any, path: str) -> None:
    """
    Scenario: "?" opens the shortcuts overlay on any admin page
      Given the dashboard, a list and an edit form
      When  each page renders
      Then  exactly one native <dialog> shortcuts-overlay is on the page, labelled by its title
      And   it is rendered before shortcuts.js runs (deferred), so the script finds it
    """
    html = client.get(path).text

    assert html.count('data-testid="shortcuts-overlay"') == 1
    dialog = _overlay(html)
    assert 'aria-labelledby="ha-shortcuts-title"' in dialog
    assert 'id="ha-shortcuts-title">Keyboard shortcuts</h2>' in dialog
    assert '<form method="dialog">' in dialog


def test_the_overlay_holds_the_single_key_switch(client: Any) -> None:
    """
    Scenario: single-key shortcuts can be turned off
      Given the shortcuts overlay
      When  it renders
      Then  it holds a switch (role=switch, shortcuts-toggle) labelled "Single-key shortcuts"
      And   data-labels translates the scope names and the registered descriptions
    """
    dialog = _overlay(client.get("/admin/keysorder").text)

    switch = re.search(r"<label class=\"ha-switch\">(.*?)</label>", dialog, re.DOTALL)
    assert switch
    assert 'role="switch"' in switch.group(1)
    assert 'data-testid="shortcuts-toggle"' in switch.group(1)
    assert "Single-key shortcuts" in switch.group(1)
    labels = json.loads(unescape(re.search(r"data-labels='([^']*)'", dialog).group(1)))
    assert labels["global"] == "General"
    assert labels["list"] == "List"
    assert labels["form"] == "Form"
    for description in ("Next row", "Previous row", "Select row", "Create new", "Save"):
        assert labels[description] == description


def test_shortcuts_script_registers_the_list_keys() -> None:
    """
    Scenario: j/k move between rows and Enter opens one
      Given static/js/shortcuts.js
      When  it is read
      Then  j, k, x and c are single-key list shortcuts, only on list pages
      And   "?" is single-key while Cmd/Ctrl+/ always opens the overlay
      And   the overlay does not open over another modal dialog
      And   the list keys do nothing while a modal dialog is open
    """
    js = SCRIPT.read_text()

    assert "single: true, scope: 'list'" in js
    for key, description in (
        ("j", "Next row"),
        ("k", "Previous row"),
        ("x", "Select row"),
        ("c", "Create new"),
    ):
        assert f"listKey('{key}', '{description}'" in js
    assert "keys: '?', single: true" in js
    assert "keys: 'mod+/'" in js
    assert "document.getElementById('list-container')" in js
    assert "document.querySelector('dialog[open]')" in js
    assert "var t = !document.querySelector('dialog[open]') && find();" in js
    assert '[data-testid="row-link"]' in js
    assert 'input[name="ids"][data-testid="bulk-checkbox"]' in js
