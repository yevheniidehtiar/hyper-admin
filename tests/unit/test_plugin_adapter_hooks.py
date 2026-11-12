"""Adapter-call plugin hooks wrap every adapter operation.

SDD ``docs/specs/plugin-registry.md``, "Adapter wrapping strategy".
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
from hyperadmin.core.plugins import _AdapterHookWrapper, wrap_adapter_with_hooks
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class AdapterHookItem(SQLModel, table=True):
    __tablename__ = "test_adapter_hook_item"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class AdapterHookItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _Recorder:
    name = "adapter-recorder"

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def on_register(self, admin: Any) -> None:
        return None

    def on_before_adapter_call(self, **kw: Any) -> None:
        self.events.append(("before", kw))

    def on_after_adapter_call(self, **kw: Any) -> None:
        self.events.append(("after", kw))

    def ops(self, phase: str) -> list[str]:
        return [kw["op"] for p, kw in self.events if p == phase]


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _build(plugin: Any | None) -> tuple[Admin, TestClient]:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(create_schema)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    if plugin is not None:
        assert admin.plugins.register(plugin, admin=admin)
    site.register(AdapterHookItem, AdapterHookItemAdmin)
    admin.mount(path="/admin")
    return admin, TestClient(app)


def test_adapter_call_hooks_wrap_every_crud_operation() -> None:
    """
    Scenario: adapter call hooks wrap every CRUD operation
      Given a plugin records (op, model) in on_before/after_adapter_call
      When  the list, create, update, delete views are exercised once each
      Then  the recorded ops include list, create, update, delete in order
      And   each before precedes its matching after
    """
    recorder = _Recorder()
    _, client = _build(recorder)

    assert client.get("/admin/adapterhookitem").status_code == 200
    created = client.post("/admin/adapterhookitem", data={"name": "a"}, follow_redirects=False)
    assert created.status_code == 303
    updated = client.put("/admin/adapterhookitem/1", data={"name": "b"}, follow_redirects=False)
    assert updated.status_code == 303
    deleted = client.delete("/admin/adapterhookitem/1", follow_redirects=False)
    assert deleted.status_code in (200, 303)
    assert recorder.events, "no adapter-call hook fired"

    before = recorder.ops("before")
    for op in ("list", "create", "update", "delete"):
        assert op in before
    firsts = [before.index(op) for op in ("list", "create", "update", "delete")]
    assert firsts == sorted(firsts)
    assert recorder.ops("after")
    assert {kw["model"] for _, kw in recorder.events} == {AdapterHookItem}
    # Each call is bracketed: before then after, never interleaved.
    phases = [p for p, _ in recorder.events]
    assert phases[::2] == ["before"] * (len(phases) // 2)
    assert phases[1::2] == ["after"] * (len(phases) // 2)


def test_wrapper_is_transparent_when_no_plugin_listens() -> None:
    """
    Scenario: wrapper is transparent when no plugins are loaded
      Given an Admin whose plugins implement no adapter-call hook
      When  a model is registered
      Then  the view's adapter is not an _AdapterHookWrapper
    """
    adapter = object()
    admin, _ = _build(None)
    wrapped = wrap_adapter_with_hooks(
        adapter, plugins=admin.plugins, dispatch=admin.dispatch_hook, model=AdapterHookItem
    )
    assert wrapped is adapter
    assert (
        wrap_adapter_with_hooks(
            adapter, plugins=None, dispatch=admin.dispatch_hook, model=AdapterHookItem
        )
        is adapter
    )


class _FailingAdapter:
    pk = "pk-value"

    async def get(self, pk: Any) -> Any:
        raise RuntimeError("boom")

    async def list(self, page: int = 1) -> list[Any]:
        return [page]


@pytest.mark.anyio
async def test_after_hook_fires_with_error_and_exception_bubbles() -> None:
    """
    Scenario: a failing adapter call still closes the hook pair
      Given a wrapped adapter whose get raises
      When  get is awaited
      Then  on_after_adapter_call receives the error and result None
      And   the exception propagates
    """
    calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(hook: str, **kw: Any) -> None:
        calls.append((hook, kw))

    wrapper = _AdapterHookWrapper(inner=_FailingAdapter(), dispatch=dispatch, model=AdapterHookItem)
    with pytest.raises(RuntimeError, match="boom"):
        await wrapper.get(7)
    assert [h for h, _ in calls] == ["on_before_adapter_call", "on_after_adapter_call"]
    assert calls[0][1]["kwargs"] == {"args": (7,)}
    assert isinstance(calls[1][1]["error"], RuntimeError)
    assert calls[1][1]["result"] is None

    assert await wrapper.list(page=3) == [3]
    assert calls[2][1]["kwargs"] == {"page": 3}
    assert calls[3][1]["result"] == [3]
    assert calls[3][1]["error"] is None


def test_unhooked_attributes_and_writes_forward_to_inner() -> None:
    """
    Scenario: non-call attributes pass through the wrapper
      Given a wrapped adapter
      When  an attribute is read and another is assigned
      Then  the read comes from, and the write lands on, the inner adapter
    """
    inner = _FailingAdapter()
    wrapper = _AdapterHookWrapper(inner=inner, dispatch=lambda *a, **k: None, model=AdapterHookItem)
    assert wrapper.pk == "pk-value"
    wrapper.count_cache_ttl = 5  # type: ignore[attr-defined]
    assert inner.count_cache_ttl == 5  # type: ignore[attr-defined]
