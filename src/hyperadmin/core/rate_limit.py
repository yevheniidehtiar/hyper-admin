"""Rate limiting: a storage seam and a per-process token-bucket implementation.

``RateLimitMiddleware`` (``hyperadmin.views.rate_limit``) asks a :class:`RateLimiter`
whether a client may proceed. Hosts with several workers can supply a shared
implementation (for example Redis-backed) without touching the middleware.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of one :meth:`RateLimiter.acquire` call."""

    allowed: bool
    #: Whole seconds until a denied client may retry; ``0`` when ``allowed``.
    retry_after: int = 0


@runtime_checkable
class RateLimiter(Protocol):
    """Decides whether the client behind ``key`` may make one more request.

    A single atomic call both checks and records the request, so concurrent requests
    cannot all pass a check made before any of them is counted.
    """

    async def acquire(self, key: str) -> RateLimitDecision:
        """Count one request for ``key`` and return whether it is allowed."""
        raise NotImplementedError


class InMemoryRateLimiter:
    """Per-process token bucket: ``requests_per_window`` requests per ``window_seconds``.

    Each key holds a bucket of ``requests_per_window`` tokens that refills evenly over
    the window, so a client may burst up to the limit and then sustains the average
    rate. State lives in this process only: with N workers a client gets up to N times
    the limit. Keys are bounded by ``max_keys``; the least recently seen is dropped
    first. ``acquire`` never awaits, so it is safe to call from concurrent tasks on
    one event loop.
    """

    def __init__(
        self,
        requests_per_window: int,
        window_seconds: int = 60,
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        for name, value in (
            ("requests_per_window", requests_per_window),
            ("window_seconds", window_seconds),
            ("max_keys", max_keys),
        ):
            if value < 1:
                msg = f"{name} must be >= 1, got {value}"
                raise ValueError(msg)
        self._capacity = float(requests_per_window)
        self._refill_per_second = requests_per_window / window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    async def acquire(self, key: str) -> RateLimitDecision:
        now = self._clock()
        tokens, updated = self._buckets.get(key, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - updated) * self._refill_per_second)
        allowed = tokens >= 1
        if allowed:
            tokens -= 1
        self._buckets[key] = (tokens, now)
        self._buckets.move_to_end(key)
        while len(self._buckets) > self._max_keys:
            self._buckets.popitem(last=False)
        if allowed:
            return RateLimitDecision(allowed=True)
        return RateLimitDecision(
            allowed=False, retry_after=math.ceil((1 - tokens) / self._refill_per_second)
        )
