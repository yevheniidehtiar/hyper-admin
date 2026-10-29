"""Emission seam: publish CRUD events from the adapter write paths.

``EventEmittingAdapter`` is a delegating proxy around any ``BaseAdapter``. After
a successful ``create`` / ``update`` / ``delete`` / ``save_inline_rows`` it hands
a ``RealtimeEvent`` to a ``RealtimeEmitter``, which publishes it on the model's
CRUD channel in a background task. Publishing is fire-and-forget: a failing
backend is logged at WARNING and never fails the write.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from hyperadmin.core.adapters import current_queryset_scope
from hyperadmin.realtime.events import RealtimeAction, RealtimeEvent, crud_channel

if TYPE_CHECKING:
    from hyperadmin.core.options import AdminOptions
    from hyperadmin.realtime.config import RealtimeSettings
    from hyperadmin.realtime.pubsub import PubSubBackend

logger = logging.getLogger(__name__)


def notifications_enabled(options: AdminOptions, settings: RealtimeSettings) -> bool:
    """Per-model override when set, else the global ``RealtimeSettings.notifications``."""
    if options.realtime_notifications is not None:
        return options.realtime_notifications
    return settings.notifications


class RealtimeEmitter:
    """Publishes events in background tasks, never propagating failures."""

    def __init__(self, pubsub: PubSubBackend, channel_prefix: str) -> None:
        self._pubsub = pubsub
        self._prefix = channel_prefix
        self._pending: set[asyncio.Task[None]] = set()

    def schedule(self, event: RealtimeEvent) -> None:
        """Publish ``event`` in the background; dropped (and logged) without a running loop."""
        try:
            task = asyncio.get_running_loop().create_task(self._publish(event))
        except RuntimeError:
            logger.debug(
                "No running event loop; dropping %s event for %s",
                event.action.value,
                event.model_name,
            )
            return
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _publish(self, event: RealtimeEvent) -> None:
        try:
            await self._pubsub.publish(
                crud_channel(event.model_name, self._prefix), event.to_bytes()
            )
        except Exception:
            logger.warning(
                "Failed to publish %s event for %s",
                event.action.value,
                event.model_name,
                exc_info=True,
            )

    async def drain(self) -> None:
        """Wait for every in-flight publish to finish."""
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)


def _actor_id() -> str | None:
    scope = current_queryset_scope()
    if scope is None:
        return None
    user_key = getattr(getattr(scope.request, "state", None), "user_key", None)
    return None if user_key is None else str(user_key)


class EventEmittingAdapter:
    """Delegating proxy that emits a ``RealtimeEvent`` after each successful write."""

    def __init__(self, inner: Any, emitter: RealtimeEmitter) -> None:
        object.__setattr__(self, "_ha_inner", inner)
        object.__setattr__(self, "_ha_emitter", emitter)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_ha_inner"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_ha_inner"), name, value)

    def _emit(self, action: RealtimeAction, pk: Any, *, from_instance: bool = False) -> None:
        inner = object.__getattribute__(self, "_ha_inner")
        try:
            event = RealtimeEvent(
                model_name=inner.model.__name__,
                pk=inner.pk.to_str(getattr(pk, inner.pk.attr) if from_instance else pk),
                action=action,
                actor_id=_actor_id(),
            )
        except Exception:
            logger.debug("Could not build %s event; skipping", action.value, exc_info=True)
            return
        object.__getattribute__(self, "_ha_emitter").schedule(event)

    async def create(self, data: dict[str, Any]) -> Any:
        instance = await object.__getattribute__(self, "_ha_inner").create(data)
        self._emit(RealtimeAction.CREATED, instance, from_instance=True)
        return instance

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        result = await object.__getattribute__(self, "_ha_inner").update(pk, data)
        self._emit(RealtimeAction.UPDATED, pk)
        return result

    async def delete(self, pk: Any) -> None:
        await object.__getattribute__(self, "_ha_inner").delete(pk)
        self._emit(RealtimeAction.DELETED, pk)

    async def save_inline_rows(self, spec: Any, rows: list[dict[str, Any]], parent_pk: Any) -> Any:
        result = await object.__getattribute__(self, "_ha_inner").save_inline_rows(
            spec, rows, parent_pk
        )
        self._emit(RealtimeAction.UPDATED, parent_pk)
        return result
