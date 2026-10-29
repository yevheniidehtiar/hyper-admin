"""RealtimeSettings pub/sub selection and notification settings (#310)."""

from __future__ import annotations

import pytest

from hyperadmin.realtime import InMemoryPubSub, RealtimeSettings
from hyperadmin.realtime.pubsub_redis import RedisPubSub

pytestmark = pytest.mark.anyio


def test_notification_defaults() -> None:
    """
    Scenario: notification settings default to on with the hyperadmin prefix
      Given RealtimeSettings()
      Then  notifications is True, channel_prefix is "hyperadmin:" and no pubsub is set
    """
    settings = RealtimeSettings()
    assert settings.notifications is True
    assert settings.channel_prefix == "hyperadmin:"
    assert settings.pubsub is None
    assert settings.pubsub_redis_url is None


async def test_resolve_pubsub_prefers_explicit_backend() -> None:
    """
    Scenario: an explicit pubsub wins over a Redis URL
      Given settings with both pubsub and pubsub_redis_url
      When  resolve_pubsub() is called
      Then  the explicit backend is returned
    """
    explicit = InMemoryPubSub()
    settings = RealtimeSettings(pubsub=explicit, pubsub_redis_url="redis://localhost:6379/1")
    assert settings.resolve_pubsub() is explicit


async def test_resolve_pubsub_uses_redis_when_url_set() -> None:
    """
    Scenario: pubsub_redis_url selects RedisPubSub
      Given settings with only pubsub_redis_url
      When  resolve_pubsub() is called
      Then  a RedisPubSub is returned
    """
    backend = RealtimeSettings(pubsub_redis_url="redis://localhost:6379/1").resolve_pubsub()
    assert isinstance(backend, RedisPubSub)
    await backend.close()


async def test_resolve_pubsub_defaults_to_in_memory() -> None:
    """
    Scenario: zero-config resolves to in-memory pub/sub
      Given RealtimeSettings()
      When  resolve_pubsub() is called
      Then  an InMemoryPubSub is returned
    """
    assert isinstance(RealtimeSettings().resolve_pubsub(), InMemoryPubSub)
