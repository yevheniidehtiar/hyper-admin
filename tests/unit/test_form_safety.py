"""Unsaved-changes guard, sticky save bar and Cmd/Ctrl+S (st-v059-kbd-01).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Form safety (kbd-01)"). The
create, edit and popup-create forms carry ``data-ha-guard`` (the leave prompt)
unless ``AdminOptions(warn_unsaved_changes=False)``; ``static/js/form_guard.js``
does the rest in the browser (covered by ``tests/e2e/test_form_safety.py``).
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

STATIC = Path(hyperadmin.__file__).parent / "static"
PROMPT = "You have unsaved changes. Leave this page?"


class GuardOrder(SQLModel, table=True):
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
            session.add(GuardOrder(id=42, number="ORD-1042"))
            await session.commit()

    anyio.run(setup)
    return eng


def _client(engine: Any, **options: Any) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(GuardOrder, _Admin, options=AdminOptions(**options))
    admin.mount(path="/admin")
    return TestClient(app)


def _form_tag(html: str, testid: str) -> str:
    match = re.search(rf'<form[^>]*data-testid="{testid}"[^>]*>', html, re.DOTALL)
    assert match, f"no {testid} form"
    return match.group(0)


def test_warn_unsaved_changes_defaults_to_on() -> None:
    """
    Scenario: the guard is on unless a model opts out
      Given an AdminOptions without arguments
      When  warn_unsaved_changes is read
      Then  it is True, and False when passed explicitly
    """
    assert AdminOptions().warn_unsaved_changes is True
    assert AdminOptions(warn_unsaved_changes=False).warn_unsaved_changes is False


@pytest.mark.parametrize("path", ["/admin/guardorder/create", "/admin/guardorder/42/edit"])
def test_create_and_edit_forms_carry_the_guard(engine, path: str) -> None:
    """
    Scenario: leaving a dirty form asks first
      Given the default options
      When  the create or edit form renders
      Then  the model form carries data-ha-guard with the translated leave prompt
      And   form_guard.js is loaded once, after shortcuts.js (mod+s registers on it)
    """
    html = _client(engine).get(path).text

    assert f'data-ha-guard="{PROMPT}"' in _form_tag(html, "model-form")
    assert html.count("/static/js/form_guard.js") == 1
    assert html.index("/static/js/shortcuts.js") < html.index("/static/js/form_guard.js")


@pytest.mark.parametrize("path", ["/admin/guardorder/create", "/admin/guardorder/42/edit"])
def test_the_guard_can_be_turned_off_per_model(engine, path: str) -> None:
    """
    Scenario: the guard can be turned off per model
      Given AdminOptions(warn_unsaved_changes=False)
      When  the create or edit form renders
      Then  the model form has no data-ha-guard attribute
      And   form_guard.js is still loaded, so Cmd/Ctrl+S keeps working
    """
    html = _client(engine, warn_unsaved_changes=False).get(path).text

    assert "data-ha-guard" not in _form_tag(html, "model-form")
    assert "/static/js/form_guard.js" in html


@pytest.mark.parametrize("warn", [True, False])
def test_popup_create_forms_follow_the_option(engine, warn: bool) -> None:
    """
    Scenario: popup create forms are guarded too
      Given AdminOptions(warn_unsaved_changes=<warn>) on the popup's model
      When  the create popup renders
      Then  the popup form carries data-ha-guard only when warn is on
    """
    html = (
        _client(engine, warn_unsaved_changes=warn)
        .get("/admin/guardorder/create-popup", params={"target": "order_id"})
        .text
    )

    assert ("data-ha-guard" in _form_tag(html, "popup-form")) is warn


def test_the_save_bar_is_sticky(engine) -> None:
    """
    Scenario: the save bar stays in view on long forms
      Given the edit form
      When  it renders
      Then  the form actions bar is the sticky variant (form-actions)
      And   the CSS pins it to the bottom, clear of the safe-area inset
    """
    html = _client(engine).get("/admin/guardorder/42/edit").text

    assert re.search(
        r'<div class="ha-form-actions ha-form-actions--sticky" data-testid="form-actions">', html
    )
    css = (STATIC / "css" / "_forms.css").read_text()
    rule = css[css.index(".ha-form-actions.ha-form-actions--sticky {") :]
    rule = rule[: rule.index("}")]
    assert "position: sticky" in rule
    assert "env(safe-area-inset-bottom" in rule


def test_form_guard_script_contract() -> None:
    """
    Scenario: Cmd+S saves the form and saving does not trigger the guard
      Given static/js/form_guard.js
      When  it is read
      Then  it registers mod+s on haShortcuts and submits with requestSubmit()
      And   it guards beforeunload and htmx:confirm, and marks a form clean on a 2xx answer
      And   a confirmed delete (the shared dialog) clears the guard instead of asking twice
      And   a plain (non-htmx) submit clears the guard, since it leaves the page on purpose
    """
    js = (STATIC / "js" / "form_guard.js").read_text()

    assert "keys: 'mod+s'" in js
    assert "requestSubmit()" in js
    assert "'beforeunload'" in js
    assert "'htmx:confirm'" in js
    assert "issueRequest(true)" in js
    assert "'htmx:beforeOnLoad'" in js
    assert "#ha-confirm-delete" in js
    assert "addEventListener('submit'" in js
    assert "!e.defaultPrevented" in js
