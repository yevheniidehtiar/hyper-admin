"""Locale catalogs for the v0.5.9 navigation, list and keyboard strings.

Spec: ``docs/specs/navigation-and-list-ux.md``. Catalog policy:
``docs/specs/i18n-top-20-locales.md`` (AI drafts stay ``#, fuzzy`` until a native
speaker reviews them; ``uk`` is reviewed and compiled).
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

import anyio
import pytest
from babel.messages.pofile import read_po
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.navigation import ACCESS_GROUP, PLUGINS_GROUP
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.loader import (
    LOCALE_DIR,
    load_translations,
    reset_current_translations,
    set_current_translations,
)
from hyperadmin.views.nav_pins import NavPins

LOCALES: tuple[str, ...] = tuple(
    sorted(p.name for p in LOCALE_DIR.iterdir() if (p / "LC_MESSAGES" / "messages.po").exists())
)

# The user-visible msgids v0.5.9 added: sidebar, palette, list rows, delete dialog,
# detail/edit actions, unsaved-changes guard and the shortcuts overlay.
V059_MSGIDS: tuple[str, ...] = (
    "Plugins",
    "Access",
    "Collapse sidebar",
    "Pinned",
    "Pin %(label)s",
    "Unpin %(label)s",
    "You can pin up to %(count)s pages",
    "Pins need a signed-in user",
    "Recent",
    "Models",
    "Pages",
    "%(count)s results",
    "No results",
    "Search models and pages",
    "Search models and pages…",
    "Results",
    "move",
    "open",
    "new",
    "New %(name)s",
    "Delete %(name)s?",
    "Delete this record?",
    "This cannot be undone.",
    "Delete %(name)s",
    "Open %(name)s",
    "You have unsaved changes. Leave this page?",
    "General",
    "Form",
    "Show keyboard shortcuts",
    "Focus search",
    "Next row",
    "Previous row",
    "Select row",
    "Create new",
    "or",
    "Keyboard shortcuts",
    "Single-key shortcuts",
)


class I18nOrder(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)


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
            session.add(I18nOrder(id=1))
            await session.commit()

    anyio.run(setup)
    app = FastAPI()
    admin = Admin(app=app, engine=eng, settings=HyperAdminSettings(create_tables=False))
    site.register(I18nOrder, _Admin)
    admin.mount(path="/admin")
    return TestClient(app)


def _shortcut_labels(html: str) -> dict[str, str]:
    start = html.index('<dialog id="ha-shortcuts"')
    dialog = html[start : html.index("</dialog>", start)]
    match = re.search(r"data-labels='([^']*)'", dialog)
    assert match
    labels: dict[str, str] = json.loads(unescape(match.group(1)))
    return labels


@pytest.mark.parametrize("locale", LOCALES)
def test_every_catalog_carries_the_v059_strings(locale: str) -> None:
    """
    Scenario: every locale catalog lists the v0.5.9 strings
      Given the .po catalog of a supported locale
      When  it is parsed
      Then  each v0.5.9 msgid is present
      And   outside English, each one has a translation (an AI draft or a reviewed one)
    """
    with (LOCALE_DIR / locale / "LC_MESSAGES" / "messages.po").open("rb") as fh:
        catalog = read_po(fh)

    for msgid in V059_MSGIDS:
        message = catalog.get(msgid)
        assert message is not None, f"{locale}: {msgid!r} is not in the catalog"
        if locale != "en":
            assert message.string, f"{locale}: {msgid!r} has no translation"


def test_the_shortcut_labels_follow_the_locale(client: Any) -> None:
    """
    Scenario: the shortcuts overlay labels render in the request locale
      Given a list page and the reviewed uk catalog
      When  the page renders with the locale cookie set to en, then to uk
      Then  data-labels carries the English descriptions for en
      And   the Ukrainian ones for uk
    """
    english = _shortcut_labels(client.get("/admin/i18norder").text)
    client.cookies.set("hyperadmin_locale", "uk")
    ukrainian = _shortcut_labels(client.get("/admin/i18norder").text)

    assert english["Next row"] == "Next row"
    assert english["global"] == "General"
    assert ukrainian["Next row"] == "Наступний рядок"
    assert ukrainian["Previous row"] == "Попередній рядок"
    assert ukrainian["global"] == "Загальні"
    assert ukrainian["Select row"] == "Вибрати рядок"


def test_the_sidebar_group_labels_are_extracted_and_translated() -> None:
    """
    Scenario: the lazy "Plugins" and "Access" group labels translate
      Given the gettext_lazy labels of the built-in sidebar groups
      When  they render with the uk catalog installed
      Then  they read "Плагіни" and "Доступ"
    """
    token = set_current_translations(load_translations("uk"))
    try:
        assert str(PLUGINS_GROUP) == "Плагіни"
        assert str(ACCESS_GROUP) == "Доступ"
    finally:
        reset_current_translations(token)

    assert str(PLUGINS_GROUP) == "Plugins"


def test_the_pin_refusal_detail_follows_the_locale() -> None:
    """
    Scenario: a pin request without a signed-in user is refused in the request locale
      Given a request whose state has no user_key and the uk catalog installed
      When  the pin view resolves the owner
      Then  it answers 403 with the Ukrainian detail
    """
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    token = set_current_translations(load_translations("uk"))
    try:
        with pytest.raises(HTTPException) as exc:
            NavPins._user(request)
    finally:
        reset_current_translations(token)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Щоб закріплювати сторінки, потрібно увійти"
