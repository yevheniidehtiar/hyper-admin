"""List page hooks for live CRUD notifications (story #312, client half).

Spec: docs/specs/realtime-crud-notifications.md ("Frontend").
"""

from __future__ import annotations

import json
import re

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings


class HookParty(SQLModel, table=True):
    __tablename__ = "test_hook_party"
    id: int | None = Field(default=None, primary_key=True)
    title: str


class HookCategory(SQLModel, table=True):
    __tablename__ = "test_hook_category"
    id: int | None = Field(default=None, primary_key=True)
    title: str


class HookDay(SQLModel, table=True):
    __tablename__ = "test_hook_day"
    id: int | None = Field(default=None, primary_key=True)
    title: str


class HookBox(SQLModel, table=True):
    __tablename__ = "test_hook_box"
    id: int | None = Field(default=None, primary_key=True)
    title: str


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _Quiet(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(realtime_notifications=False)


@pytest.fixture(autouse=True)
def _clean_registry():
    site._registry = {}
    yield
    site._registry = {}


def _client(realtime: RealtimeSettings | None) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            for model in (HookParty, HookCategory, HookDay, HookBox):
                session.add(model(title="Hello"))
            await session.commit()

    anyio.run(setup)
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        realtime=realtime,
    )
    site.register(HookParty, _Admin)
    site.register(HookCategory, _Admin)
    site.register(HookDay, _Admin)
    site.register(HookBox, _Quiet)
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_root_carries_the_subscription_hook_and_row_pks() -> None:
    """
    Scenario: a notifying model's list renders the hook, labels, rows and toast template
      Given realtime is on and the model has notifications enabled
      When  the list page is rendered
      Then  #model-list carries data-realtime-model and singular/plural labels
      And   every row carries data-pk
      And   the toast template and its localized strings are present
    """
    html = _client(RealtimeSettings()).get("/admin/hookparty").text

    assert 'data-realtime-model="hookparty"' in html
    assert 'data-realtime-label="HookParty"' in html
    assert 'data-realtime-label-plural="HookParties"' in html
    assert re.search(r'<tr class="ha-table-row" data-testid="list-row" data-pk="1"', html)
    assert "data-realtime-toast-template" in html
    assert 'data-testid="realtime-toast"' in html
    assert 'role="status"' in html.split("data-realtime-toast-template")[1]


@pytest.mark.parametrize(
    ("path", "plural"),
    [("hookcategory", "HookCategories"), ("hookday", "HookDays")],
)
def test_plural_label_follows_english_rules(path: str, plural: str) -> None:
    """
    Scenario: the summary toast names the plural of the model
      Given a model named HookCategory (consonant + y) or HookDay (vowel + y)
      When  its list page is rendered
      Then  the plural label is HookCategories / HookDays
    """
    html = _client(RealtimeSettings()).get(f"/admin/{path}").text

    assert f'data-realtime-label-plural="{plural}"' in html


def test_strings_json_has_plural_forms_per_category() -> None:
    """
    Scenario: the toast strings are rendered with a plural form per CLDR category
      Given realtime notifications are on
      When  the list page is rendered
      Then  the strings JSON holds single-record messages and summary forms
    """
    html = _client(RealtimeSettings()).get("/admin/hookparty").text
    raw = re.search(r"<script type=\"application/json\" data-realtime-strings>(.*?)</script>", html)
    assert raw is not None
    strings = json.loads(raw.group(1))

    assert strings["created"] == "{actor} created {model} #{pk}"
    assert strings["deleted"] == "{actor} deleted {model} #{pk}"
    assert strings["pill"] == "List changed: refresh"
    assert set(strings["summary"]) == {"zero", "one", "two", "few", "many", "other"}
    assert strings["summary"]["other"] == "{actor} changed {count} {model}"
    assert strings["people"]["other"] == "{count} people"
    assert strings["people"]["one"] == "{count} person"


def test_model_with_notifications_disabled_renders_no_hook() -> None:
    """
    Scenario: an opted-out model renders no hook
      Given a model with realtime_notifications=False
      When  its list page is rendered
      Then  there is no data-realtime-model and no toast template
      And   rows still carry data-pk
    """
    html = _client(RealtimeSettings()).get("/admin/hookbox").text

    assert "data-realtime-model" not in html
    assert "data-realtime-toast-template" not in html
    assert 'data-pk="1"' in html


def test_realtime_off_renders_no_hook_and_no_self_marker() -> None:
    """
    Scenario: without realtime the list page is unchanged
      Given Admin(realtime=None)
      When  the list page is rendered
      Then  there is no hook, no toast template and no navbar status element
    """
    html = _client(None).get("/admin/hookparty").text

    assert "data-realtime-model" not in html
    assert "data-realtime-toast-template" not in html
    assert "realtime-status" not in html
