"""Unit tests for realtime/emitting.py: emitter, proxy adapter and enablement (#310)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from hyperadmin.core.adapters import BaseAdapter, queryset_scope
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.primary_key import PrimaryKeyInfo
from hyperadmin.realtime import (
    InMemoryPubSub,
    RealtimeAction,
    RealtimeEvent,
    RealtimeSettings,
    crud_channel,
)
from hyperadmin.realtime.emitting import (
    EventEmittingAdapter,
    RealtimeEmitter,
    notifications_enabled,
)

pytestmark = pytest.mark.anyio


class Widget:
    """Stand-in model; the proxy only needs ``__name__``."""


class FakeAdapter(BaseAdapter):
    """In-memory BaseAdapter that records calls and returns objects with ``id``."""

    pk = PrimaryKeyInfo(attr="id", python_type=int, generated=True)

    def __init__(self) -> None:
        self.model = Widget
        self.engine = None
        self.session_factory = None
        self._queryset_filter = None
        self.calls: list[tuple[str, Any]] = []
        self.marker = "inner"
        self.fail = False

    async def get(self, pk: Any) -> Any:
        return SimpleNamespace(id=pk)

    async def list(self, *args: Any, **kwargs: Any) -> Any:
        return []

    async def create(self, data: dict[str, Any]) -> Any:
        self.calls.append(("create", data))
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(id=7, **data)

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        self.calls.append(("update", pk))
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(id=pk, **data)

    async def delete(self, pk: Any) -> None:
        self.calls.append(("delete", pk))
        if self.fail:
            raise RuntimeError("boom")

    async def get_related(self, pk: Any, field: str) -> list[Any]:
        return []

    async def get_schema(self) -> dict[str, Any]:
        return {"fields": []}

    async def get_choices(self, *args: Any, **kwargs: Any) -> Any:
        return []

    async def save_inline_rows(self, spec: Any, rows: list[dict[str, Any]], parent_pk: Any) -> None:
        self.calls.append(("inline", parent_pk))
        if self.fail:
            raise RuntimeError("boom")

    def to_dict(self, record: Any) -> dict[str, Any]:
        return dict(vars(record))


class BrokenPubSub(InMemoryPubSub):
    async def publish(self, channel: str, message: bytes) -> None:
        raise ConnectionError("redis down")


def _request(user_key: str | None = "alice") -> Any:
    state = SimpleNamespace() if user_key is None else SimpleNamespace(user_key=user_key)
    return SimpleNamespace(state=state)


async def _run_and_collect(proxy_call: Any, pubsub: InMemoryPubSub, emitter: Any) -> RealtimeEvent:
    async with pubsub.subscribe(crud_channel("Widget")) as messages:
        await proxy_call()
        await emitter.drain()
        return RealtimeEvent.from_bytes(await asyncio.wait_for(anext(messages), 1))


@pytest.mark.parametrize(
    ("default", "override", "expected"),
    [
        (True, None, True),
        (False, None, False),
        (True, True, True),
        (False, True, True),
        (True, False, False),
        (False, False, False),
    ],
)
def test_notifications_enabled_matrix(default: bool, override: bool | None, expected: bool) -> None:
    """
    Scenario: per-model override beats the global notifications flag
      Given RealtimeSettings.notifications=<default> and realtime_notifications=<override>
      When  notifications_enabled is evaluated
      Then  the override wins unless it is None
    """
    options = AdminOptions(realtime_notifications=override)
    settings = RealtimeSettings(notifications=default)
    assert notifications_enabled(options, settings) is expected


async def test_emitter_publishes_to_prefixed_channel_and_drains() -> None:
    """
    Scenario: scheduled events are published on the prefixed model channel
      Given an emitter with prefix "p:" over an in-memory pubsub
      When  an event is scheduled and the emitter is drained
      Then  the subscriber of crud_channel(model, "p:") receives it
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "p:")
    event = RealtimeEvent("Widget", "1", RealtimeAction.CREATED, actor_id="bob")
    async with pubsub.subscribe(crud_channel("Widget", "p:")) as messages:
        emitter.schedule(event)
        await emitter.drain()
        received = RealtimeEvent.from_bytes(await asyncio.wait_for(anext(messages), 1))
    assert received == event


async def test_emitter_drain_without_pending_is_noop() -> None:
    """
    Scenario: draining an idle emitter returns immediately
      Given an emitter with nothing scheduled
      When  drain() is awaited
      Then  it completes
    """
    await RealtimeEmitter(InMemoryPubSub(), "p:").drain()


async def test_emitter_swallows_publish_failure_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a failing backend never propagates
      Given a pubsub whose publish raises
      When  an event is scheduled and drained
      Then  no exception escapes and a WARNING names the model and action
    """
    emitter = RealtimeEmitter(BrokenPubSub(), "p:")
    with caplog.at_level(logging.WARNING):
        emitter.schedule(RealtimeEvent("Widget", "1", RealtimeAction.DELETED))
        await emitter.drain()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings
    text = warnings[0].getMessage()
    assert "Widget" in text
    assert "deleted" in text


def test_emitter_schedule_without_running_loop_drops_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: no running event loop
      Given synchronous code with no running loop
      When  an event is scheduled
      Then  it is dropped, logged, and nothing is raised
    """
    emitter = RealtimeEmitter(InMemoryPubSub(), "p:")
    with caplog.at_level(logging.DEBUG):
        emitter.schedule(RealtimeEvent("Widget", "1", RealtimeAction.CREATED))
    assert caplog.records


async def test_proxy_emits_created_updated_deleted() -> None:
    """
    Scenario: each write emits one event after the inner call succeeds
      Given a proxied adapter and a subscriber
      When  create, update and delete are called
      Then  created/updated/deleted events carry the stringified pk
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(FakeAdapter(), emitter)

    created = await _run_and_collect(lambda: proxy.create({"name": "a"}), pubsub, emitter)
    updated = await _run_and_collect(lambda: proxy.update(7, {"name": "b"}), pubsub, emitter)
    deleted = await _run_and_collect(lambda: proxy.delete(7), pubsub, emitter)

    assert (created.action, created.pk, created.model_name) == (
        RealtimeAction.CREATED,
        "7",
        "Widget",
    )
    assert (updated.action, updated.pk) == (RealtimeAction.UPDATED, "7")
    assert (deleted.action, deleted.pk) == (RealtimeAction.DELETED, "7")


async def test_proxy_inline_rows_emit_updated_for_parent() -> None:
    """
    Scenario: inline children emit as an update of the parent
      Given a proxied parent adapter
      When  save_inline_rows is called for parent pk 3
      Then  an UPDATED event for pk "3" is published
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(FakeAdapter(), emitter)
    event = await _run_and_collect(lambda: proxy.save_inline_rows(None, [], 3), pubsub, emitter)
    assert (event.action, event.pk) == (RealtimeAction.UPDATED, "3")


@pytest.mark.parametrize("method", ["create", "update", "delete", "inline"])
async def test_proxy_failed_write_emits_nothing(method: str) -> None:
    """
    Scenario: a failing write publishes nothing
      Given an inner adapter whose write raises
      When  the proxied write is called
      Then  the exception propagates and no event is scheduled
    """
    inner = FakeAdapter()
    inner.fail = True
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(inner, emitter)
    calls = {
        "create": lambda: proxy.create({}),
        "update": lambda: proxy.update(1, {}),
        "delete": lambda: proxy.delete(1),
        "inline": lambda: proxy.save_inline_rows(None, [], 1),
    }
    async with pubsub.subscribe(crud_channel("Widget")) as messages:
        with pytest.raises(RuntimeError, match="boom"):
            await calls[method]()
        await emitter.drain()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(messages), 0.05)


async def test_proxy_event_build_failure_never_fails_the_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: pk extraction failure is guarded
      Given an inner create returning an object without the pk attribute
      When  the proxied create is called
      Then  the created object is still returned and nothing is published
    """
    inner = FakeAdapter()
    marker = object()

    async def create(data: dict[str, Any]) -> Any:
        return marker

    inner.create = create  # type: ignore[method-assign]
    emitter = RealtimeEmitter(InMemoryPubSub(), "hyperadmin:")
    proxy = EventEmittingAdapter(inner, emitter)
    with caplog.at_level(logging.DEBUG):
        result = await proxy.create({})
    assert result is marker
    await emitter.drain()
    assert caplog.records


async def test_proxy_actor_id_from_queryset_scope() -> None:
    """
    Scenario: actor comes from the request-scoped user_key
      Given an active queryset scope whose request.state.user_key is "alice"
      When  the proxied update is called
      Then  the event actor_id is "alice"
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(FakeAdapter(), emitter)
    with queryset_scope(_request("alice"), lambda _m: None):
        event = await _run_and_collect(lambda: proxy.update(1, {}), pubsub, emitter)
    assert event.actor_id == "alice"


@pytest.mark.parametrize("scoped", [False, True])
async def test_proxy_actor_none_without_request_or_user_key(scoped: bool) -> None:
    """
    Scenario: no actor outside a request or without user_key
      Given no scope (or a scope whose request has no user_key)
      When  the proxied delete is called
      Then  the event actor_id is None
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(FakeAdapter(), emitter)
    if scoped:
        with queryset_scope(_request(None), lambda _m: None):
            event = await _run_and_collect(lambda: proxy.delete(1), pubsub, emitter)
    else:
        event = await _run_and_collect(lambda: proxy.delete(1), pubsub, emitter)
    assert event.actor_id is None


async def test_proxy_actor_none_when_request_has_no_state() -> None:
    """
    Scenario: a scope request without state yields no actor
      Given a scope whose request object has no state attribute
      When  the proxied delete is called
      Then  actor_id is None
    """
    pubsub = InMemoryPubSub()
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    proxy = EventEmittingAdapter(FakeAdapter(), emitter)
    with queryset_scope(SimpleNamespace(), lambda _m: None):
        event = await _run_and_collect(lambda: proxy.delete(1), pubsub, emitter)
    assert event.actor_id is None


def test_proxy_exposes_every_public_base_adapter_member() -> None:
    """
    Scenario: the proxy satisfies the whole BaseAdapter contract
      Given a proxied adapter
      When  every public BaseAdapter attribute is looked up on the proxy
      Then  each is reachable
    """
    inner = FakeAdapter()
    proxy = EventEmittingAdapter(inner, RealtimeEmitter(InMemoryPubSub(), "p:"))
    names = [n for n in dir(BaseAdapter) if not n.startswith("_")]
    assert {"pk", "list", "get", "get_schema", "for_model"} <= set(names)
    for name in names:
        member = getattr(proxy, name)
        if name in {"create", "update", "delete", "save_inline_rows"}:
            assert inspect.iscoroutinefunction(member)
    assert proxy.pk is inner.pk
    assert proxy.model is Widget
    assert proxy.get_queryset() == inner.get_queryset()


async def test_proxy_read_methods_delegate() -> None:
    """
    Scenario: reads pass straight through
      Given a proxied adapter
      When  get and get_schema are called
      Then  the inner results come back
    """
    proxy = EventEmittingAdapter(FakeAdapter(), RealtimeEmitter(InMemoryPubSub(), "p:"))
    assert (await proxy.get(5)).id == 5
    assert await proxy.get_schema() == {"fields": []}


def test_proxy_attribute_writes_reach_inner_adapter() -> None:
    """
    Scenario: attribute writes through the proxy hit the real adapter
      Given a proxied adapter
      When  view code assigns an attribute and set_queryset_filter is used
      Then  the inner adapter holds the new values
    """
    inner = FakeAdapter()
    proxy = EventEmittingAdapter(inner, RealtimeEmitter(InMemoryPubSub(), "p:"))
    proxy.marker = "changed"
    assert inner.marker == "changed"
    assert proxy.marker == "changed"

    def fn(_request: Any) -> dict[str, Any]:
        return {}

    proxy.set_queryset_filter(fn)
    assert inner._queryset_filter is fn
