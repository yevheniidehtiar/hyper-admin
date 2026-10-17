"""Unit tests for the RealtimeEvent envelope (#308)."""

from __future__ import annotations

import dataclasses
import json
from uuid import UUID

import pytest

from hyperadmin.realtime import InMemoryPubSub, PrimaryKey, RealtimeAction, RealtimeEvent

ARTICLE_UUID = UUID("12345678-1234-5678-1234-567812345678")


def test_action_enum_values() -> None:
    assert [a.value for a in RealtimeAction] == ["created", "updated", "deleted"]
    assert RealtimeAction("updated") is RealtimeAction.UPDATED


def test_event_fields() -> None:
    event = RealtimeEvent("article", 1, RealtimeAction.CREATED, "<tr></tr>")
    assert [f.name for f in dataclasses.fields(event)] == [
        "model_name",
        "pk",
        "action",
        "html_fragment",
    ]
    assert RealtimeEvent("article", 1, RealtimeAction.DELETED).html_fragment is None


def test_event_is_immutable() -> None:
    event = RealtimeEvent("article", 1, RealtimeAction.CREATED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.pk = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("pk", "expected"),
    [(42, "42"), ("slug-1", "slug-1"), (ARTICLE_UUID, str(ARTICLE_UUID))],
)
def test_to_bytes_serialises_json_with_string_pk(pk: PrimaryKey, expected: str) -> None:
    event = RealtimeEvent("article", pk, RealtimeAction.UPDATED, "<tr>x</tr>")
    payload = event.to_bytes()
    assert isinstance(payload, bytes)
    assert json.loads(payload) == {
        "model_name": "article",
        "pk": expected,
        "action": "updated",
        "html_fragment": "<tr>x</tr>",
    }


@pytest.mark.parametrize("pk", [7, "abc", ARTICLE_UUID])
def test_round_trip_stringifies_pk(pk: PrimaryKey) -> None:
    event = RealtimeEvent("article", pk, RealtimeAction.DELETED)
    restored = RealtimeEvent.from_bytes(event.to_bytes())
    assert restored == RealtimeEvent("article", str(pk), RealtimeAction.DELETED)
    assert restored.action is RealtimeAction.DELETED


def test_round_trip_preserves_unicode_fragment() -> None:
    event = RealtimeEvent("article", "1", RealtimeAction.CREATED, "<td>café ✓</td>")
    assert RealtimeEvent.from_bytes(event.to_bytes()) == event


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"\xff\xfe",
        b"[]",
        b'{"pk": "1", "action": "created"}',
        b'{"model_name": "", "pk": "1", "action": "created"}',
        b'{"model_name": "a", "pk": 1, "action": "created"}',
        b'{"model_name": "a", "pk": "1", "action": "archived"}',
        b'{"model_name": "a", "pk": "1", "action": "created", "html_fragment": 3}',
    ],
)
def test_from_bytes_rejects_malformed_payload(payload: bytes) -> None:
    with pytest.raises(ValueError, match=r"RealtimeEvent|RealtimeAction"):
        RealtimeEvent.from_bytes(payload)


@pytest.mark.anyio
async def test_event_travels_over_pubsub() -> None:
    backend = InMemoryPubSub()
    event = RealtimeEvent("article", ARTICLE_UUID, RealtimeAction.CREATED, "<tr></tr>")
    async with backend.subscribe("crud:article") as messages:
        await backend.publish("crud:article", event.to_bytes())
        received = RealtimeEvent.from_bytes(await anext(messages))
    assert received.pk == str(ARTICLE_UUID)
    assert received.html_fragment == "<tr></tr>"
