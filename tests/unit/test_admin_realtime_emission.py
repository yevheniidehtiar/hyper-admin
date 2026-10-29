"""Admin wiring for CRUD event emission (#310)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

import hyperadmin.core.app as app_module
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import (
    InMemoryPubSub,
    RealtimeAction,
    RealtimeEvent,
    RealtimeSettings,
    crud_channel,
)
from hyperadmin.realtime.emitting import RealtimeEmitter


class AwNote(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    body: str


class AwQuiet(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    body: str


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def clean_registry():
    site._registry = {}
    yield
    site._registry = {}


def _admin(realtime: RealtimeSettings | None) -> Admin:
    return Admin(
        app=FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite://"),
        settings=HyperAdminSettings(create_tables=False),
        realtime=realtime,
    )


def test_admin_shares_one_pubsub_with_ws_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: the WS handler and the emitter use the same pubsub
      Given Admin(realtime=RealtimeSettings(pubsub=P))
      When  the admin is mounted
      Then  make_ws_handler receives pubsub=P
    """
    captured: dict[str, Any] = {}
    real = app_module.make_ws_handler

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(app_module, "make_ws_handler", spy)
    pubsub = InMemoryPubSub()
    admin = _admin(RealtimeSettings(pubsub=pubsub))
    admin.mount("/admin")
    assert captured["pubsub"] is pubsub
    assert admin._realtime_pubsub is pubsub
    assert isinstance(admin._realtime_emitter, RealtimeEmitter)


def test_admin_without_realtime_has_no_emitter() -> None:
    """
    Scenario: realtime off leaves emission machinery unset
      Given Admin(realtime=None)
      Then  there is no pubsub and no emitter
    """
    admin = _admin(None)
    assert admin._realtime_pubsub is None
    assert admin._realtime_emitter is None


def test_mount_collects_notification_models() -> None:
    """
    Scenario: mounted models that emit are tracked
      Given two models, one opted out of notifications
      When  the admin is mounted
      Then  only the opted-in lowercased model name is tracked
    """
    site.register(AwNote, _Admin, options=AdminOptions())
    site.register(AwQuiet, _Admin, options=AdminOptions(realtime_notifications=False))
    admin = _admin(RealtimeSettings(pubsub=InMemoryPubSub()))
    admin.mount("/admin")
    assert admin._notification_models == {"awnote"}


@pytest.mark.anyio
async def test_publish_event_is_noop_when_realtime_disabled() -> None:
    """
    Scenario: publish_event is harmless with realtime off
      Given Admin(realtime=None)
      When  publish_event is called
      Then  nothing is raised
    """
    _admin(None).publish_event(RealtimeEvent("AwNote", "1", RealtimeAction.UPDATED))


@pytest.mark.anyio
async def test_publish_event_ignores_models_without_notifications() -> None:
    """
    Scenario: events for non-enabled models are dropped
      Given realtime is on but "AwNote" is not an enabled model
      When  publish_event is called for it
      Then  no message is published
    """
    pubsub = InMemoryPubSub()
    admin = _admin(RealtimeSettings(pubsub=pubsub))
    async with pubsub.subscribe(crud_channel("AwNote")) as messages:
        admin.publish_event(RealtimeEvent("AwNote", "1", RealtimeAction.UPDATED))
        await admin._realtime_emitter.drain()  # type: ignore[union-attr]
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(messages), 0.05)


@pytest.mark.anyio
async def test_publish_event_schedules_for_enabled_model() -> None:
    """
    Scenario: a custom event is published for an enabled model
      Given "awnote" is an enabled notification model
      When  publish_event is called with a case-differing model_name
      Then  the subscriber of the prefixed channel receives it
    """
    pubsub = InMemoryPubSub()
    admin = _admin(RealtimeSettings(pubsub=pubsub, channel_prefix="t:"))
    admin._notification_models.add("awnote")
    event = RealtimeEvent("AwNote", "9", RealtimeAction.UPDATED, actor_id="sys")
    async with pubsub.subscribe(crud_channel("AwNote", "t:")) as messages:
        admin.publish_event(event)
        await admin._realtime_emitter.drain()  # type: ignore[union-attr]
        received = RealtimeEvent.from_bytes(await asyncio.wait_for(anext(messages), 1))
    assert received == event


@pytest.mark.anyio
async def test_shutdown_drains_emitter_then_closes_pubsub() -> None:
    """
    Scenario: shutdown flushes pending events and closes the backend
      Given a pending scheduled event
      When  admin.shutdown() runs
      Then  the event was delivered and the pubsub is closed
    """
    pubsub = InMemoryPubSub()
    admin = _admin(RealtimeSettings(pubsub=pubsub))
    admin._notification_models.add("awnote")
    async with pubsub.subscribe(crud_channel("AwNote")) as messages:
        admin.publish_event(RealtimeEvent("AwNote", "1", RealtimeAction.CREATED))
        await admin.shutdown()
        received = RealtimeEvent.from_bytes(await asyncio.wait_for(anext(messages), 1))
    assert received.pk == "1"
    with pytest.raises(RuntimeError, match="closed"):
        await pubsub.publish("x", b"y")
