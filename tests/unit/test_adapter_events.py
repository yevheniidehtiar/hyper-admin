"""CRUD event emission through real adapters on a real async SQLite engine (#310)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import queryset_scope
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.realtime import (
    InMemoryPubSub,
    RealtimeAction,
    RealtimeEvent,
    crud_channel,
)
from hyperadmin.realtime.emitting import EventEmittingAdapter, RealtimeEmitter

pytestmark = pytest.mark.anyio


class EvBoard(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    title: str


class EvCard(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    label: str
    ev_board_id: int | None = Field(default=None, foreign_key="evboard.id")


class BrokenPubSub(InMemoryPubSub):
    async def publish(self, channel: str, message: bytes) -> None:
        raise ConnectionError("redis down")


@pytest.fixture
async def engine() -> AsyncIterator[Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(params=[SQLModelAdapter, SQLAlchemyAdapter], ids=["sqlmodel", "sqlalchemy"])
def adapter_cls(request: pytest.FixtureRequest) -> Any:
    return request.param


def _wrap(adapter_cls: Any, engine: Any, model: Any, pubsub: Any) -> tuple[Any, RealtimeEmitter]:
    emitter = RealtimeEmitter(pubsub, "hyperadmin:")
    inner = adapter_cls(model=model, session_factory=async_sessionmaker(engine))
    return EventEmittingAdapter(inner, emitter), emitter


async def _next(messages: Any) -> RealtimeEvent:
    return RealtimeEvent.from_bytes(await asyncio.wait_for(anext(messages), 1))


def _request(user_key: str) -> Any:
    return SimpleNamespace(state=SimpleNamespace(user_key=user_key))


async def test_create_update_delete_emit_events_with_pk_and_actor(
    adapter_cls: Any, engine: Any
) -> None:
    """
    Scenario: writes through the proxied adapter publish CRUD events
      Given a proxied adapter and a subscriber on the model channel
      And   a request scope whose user_key is "alice"
      When  a board is created, renamed and deleted
      Then  created, updated and deleted events arrive with the board pk and actor "alice"
    """
    pubsub = InMemoryPubSub()
    adapter, emitter = _wrap(adapter_cls, engine, EvBoard, pubsub)

    async with pubsub.subscribe(crud_channel("EvBoard")) as messages:
        with queryset_scope(_request("alice"), lambda _m: None):
            board = await adapter.create({"title": "Todo"})
            await adapter.update(board.id, {"title": "Done"})
            await adapter.delete(board.id)
        await emitter.drain()
        events = [await _next(messages) for _ in range(3)]

    assert [e.action for e in events] == [
        RealtimeAction.CREATED,
        RealtimeAction.UPDATED,
        RealtimeAction.DELETED,
    ]
    assert {e.pk for e in events} == {str(board.id)}
    assert {e.model_name for e in events} == {"EvBoard"}
    assert {e.actor_id for e in events} == {"alice"}


async def test_actor_is_none_outside_a_request(adapter_cls: Any, engine: Any) -> None:
    """
    Scenario: writes outside a request carry no actor
      Given a proxied adapter and no active request scope
      When  a board is created
      Then  the event has actor_id None
    """
    pubsub = InMemoryPubSub()
    adapter, emitter = _wrap(adapter_cls, engine, EvBoard, pubsub)
    async with pubsub.subscribe(crud_channel("EvBoard")) as messages:
        await adapter.create({"title": "x"})
        await emitter.drain()
        event = await _next(messages)
    assert event.actor_id is None


async def test_inline_save_emits_updated_for_parent(adapter_cls: Any, engine: Any) -> None:
    """
    Scenario: saving inline rows emits an update of the parent
      Given a board with a card form row
      When  save_inline_rows is called on the proxied board adapter
      Then  an UPDATED event for the board pk is published
    """
    pubsub = InMemoryPubSub()
    adapter, emitter = _wrap(adapter_cls, engine, EvBoard, pubsub)
    board = await adapter.create({"title": "b"})
    await emitter.drain()
    spec = InlineModelSpec(model=EvCard, fk_field="ev_board_id")
    async with pubsub.subscribe(crud_channel("EvBoard")) as messages:
        await adapter.save_inline_rows(spec, [{"label": "c1"}], parent_pk=board.id)
        await emitter.drain()
        event = await _next(messages)
    assert (event.action, event.pk) == (RealtimeAction.UPDATED, str(board.id))


async def test_failed_update_publishes_nothing(adapter_cls: Any, engine: Any) -> None:
    """
    Scenario: a failing update emits no event
      Given a proxied adapter
      When  update is called with a malformed primary key
      Then  the error propagates and nothing is published
    """
    pubsub = InMemoryPubSub()
    adapter, emitter = _wrap(adapter_cls, engine, EvBoard, pubsub)
    async with pubsub.subscribe(crud_channel("EvBoard")) as messages:
        with pytest.raises(Exception):  # noqa: B017, PT011 - InvalidPrimaryKey
            await adapter.update("not-an-int", {"title": "x"})
        await emitter.drain()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(messages), 0.05)


async def test_publish_failure_never_fails_the_write(
    adapter_cls: Any, engine: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a broken pubsub backend does not break CRUD
      Given a proxied adapter whose pubsub publish raises
      When  a board is created
      Then  the row is persisted and returned
      And   a WARNING is logged
    """
    adapter, emitter = _wrap(adapter_cls, engine, EvBoard, BrokenPubSub())
    with caplog.at_level(logging.WARNING):
        board = await adapter.create({"title": "survives"})
        await emitter.drain()
    assert board.id is not None
    assert (await adapter.get(board.id)).title == "survives"
    assert any(r.levelno == logging.WARNING for r in caplog.records)
