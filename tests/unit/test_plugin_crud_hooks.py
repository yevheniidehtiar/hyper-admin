"""App-level plugin hooks fire around the create / update / delete views.

SDD ``docs/specs/plugin-registry.md``, hook table.
"""

from __future__ import annotations

from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class HookItem(SQLModel, table=True):
    __tablename__ = "test_hook_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class HookItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _Recorder:
    name = "recorder"

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def on_register(self, admin: Any) -> None:
        return None

    def _record(self, hook: str, **kwargs: Any) -> None:
        self.events.append((hook, kwargs))

    def on_before_create(self, **kw: Any) -> None:
        self._record("before_create", **kw)

    def on_after_create(self, **kw: Any) -> None:
        self._record("after_create", **kw)

    def on_before_update(self, **kw: Any) -> None:
        self._record("before_update", **kw)

    def on_after_update(self, **kw: Any) -> None:
        self._record("after_update", **kw)

    def on_before_delete(self, **kw: Any) -> None:
        self._record("before_delete", **kw)

    def on_after_delete(self, **kw: Any) -> None:
        self._record("after_delete", **kw)

    @property
    def order(self) -> list[str]:
        return [hook for hook, _ in self.events]


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def setup() -> tuple[TestClient, _Recorder]:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(create_schema)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    recorder = _Recorder()
    assert admin.plugins.register(recorder, admin=admin)
    site.register(HookItem, HookItemAdmin)
    admin.mount(path="/admin")
    return TestClient(app), recorder


def _create(client: TestClient, name: str = "a") -> None:
    response = client.post("/admin/hookitem", data={"name": name}, follow_redirects=False)
    assert response.status_code == 303


def test_create_fires_before_then_after(setup: tuple[TestClient, _Recorder]) -> None:
    """
    Scenario: on_before_create fires before adapter create, on_after_create after
      Given a plugin records create hooks
      When  POST /admin/hookitem with valid data
      Then  the order is before_create, after_create
      And   the after hook receives the stored instance
    """
    client, recorder = setup
    _create(client)
    assert recorder.order == ["before_create", "after_create"]
    before, after = recorder.events[0][1], recorder.events[1][1]
    assert before["model"] is HookItem
    assert before["data"]["name"] == "a"
    assert before["admin"] is not None
    assert after["instance"].id == 1


def test_validation_failure_fires_no_hook(setup: tuple[TestClient, _Recorder]) -> None:
    """
    Scenario: validation failure prevents on_before_create from firing
      Given a required field is missing
      When  POST /admin/hookitem
      Then  the form is re-rendered with 422 and no hook was called
    """
    client, recorder = setup
    response = client.post("/admin/hookitem", data={}, follow_redirects=False)
    assert response.status_code == 422
    assert recorder.events == []


def test_update_hooks_receive_pk_and_instance(setup: tuple[TestClient, _Recorder]) -> None:
    """
    Scenario: on_after_update hook receives the updated instance
      Given an item with id 1 exists
      When  it is updated through the form
      Then  before_update gets pk 1 and after_update gets the instance with id 1
    """
    client, recorder = setup
    _create(client)
    recorder.events.clear()
    response = client.put("/admin/hookitem/1", data={"name": "b"}, follow_redirects=False)
    assert response.status_code == 303
    assert recorder.order == ["before_update", "after_update"]
    assert recorder.events[0][1]["pk"] == 1
    assert recorder.events[0][1]["data"]["name"] == "b"
    assert recorder.events[1][1]["instance"].id == 1


def test_delete_hooks_fire_in_order(setup: tuple[TestClient, _Recorder]) -> None:
    """
    Scenario: on_before_delete fires before delete; on_after_delete fires after
      Given an item with id 1 exists
      When  it is deleted
      Then  the recorded order is before_delete, after_delete, both with pk 1
    """
    client, recorder = setup
    _create(client)
    recorder.events.clear()
    response = client.delete("/admin/hookitem/1", follow_redirects=False)
    assert response.status_code == 303
    assert recorder.order == ["before_delete", "after_delete"]
    assert [kw["pk"] for _, kw in recorder.events] == [1, 1]


def test_view_without_dispatcher_is_a_noop() -> None:
    """
    Scenario: a view built without an admin fires nothing
      Given a view with no hook dispatcher
      When  a hook is fired
      Then  nothing happens
    """
    from hyperadmin.views.dynamic.core import DynamicModelView

    view = DynamicModelView.__new__(DynamicModelView)
    view._hook_dispatcher = None
    view.model = HookItem
    view._fire_hook("on_before_create", data={})
