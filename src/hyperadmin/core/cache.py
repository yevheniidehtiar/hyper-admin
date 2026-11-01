"""Count cache: a small TTL cache for list totals.

``count(*)`` on a large table can cost seconds and its result is the same for every
page of the same query, so adapters may cache it for a few seconds. The cache is
keyed by model first (``key[0]``), which lets a write evict every entry of one model.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable


@runtime_checkable
class CountCache(Protocol):
    """Storage seam for cached list totals. ``key[0]`` is the model's qualified name."""

    async def get(self, key: tuple[Hashable, ...]) -> int | None:
        """Return the cached total, or ``None`` when absent or expired."""
        ...

    async def set(self, key: tuple[Hashable, ...], value: int, ttl: int) -> None:
        """Store ``value`` for ``ttl`` seconds."""
        ...

    async def invalidate_model(self, model_qualname: str) -> None:
        """Drop every entry whose ``key[0]`` is ``model_qualname``."""
        ...


class InMemoryTTLCache:
    """Per-process LRU cache whose entries also expire after their TTL.

    Bounded by ``max_entries`` so a site with many distinct filter combinations cannot
    grow it without limit; the least recently used entry is dropped first.
    """

    def __init__(
        self, max_entries: int = 1024, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if max_entries < 1:
            msg = f"max_entries must be >= 1, got {max_entries}"
            raise ValueError(msg)
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[tuple[Hashable, ...], tuple[int, float]] = OrderedDict()

    async def get(self, key: tuple[Hashable, ...]) -> int | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    async def set(self, key: tuple[Hashable, ...], value: int, ttl: int) -> None:
        self._entries[key] = (value, self._clock() + ttl)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    async def invalidate_model(self, model_qualname: str) -> None:
        for key in [k for k in self._entries if k[0] == model_qualname]:
            del self._entries[key]
