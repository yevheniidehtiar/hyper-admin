"""Per-worker TTL cache for the authenticated user and its permission set.

Opt-in through ``HyperAdminSettings.user_cache_ttl``. The cache lives in one
process: a write on this worker drops the affected entries at commit, while other
workers may serve a stale entry for up to the TTL (see the production notes).
"""

from __future__ import annotations

import time
import weakref
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, NamedTuple

from sqlalchemy import event
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from collections.abc import Callable

#: Upper bound on cached users per middleware instance; the oldest entry is evicted first.
DEFAULT_MAX_ENTRIES = 1024

_DIRTY_KEY = "hyperadmin_user_cache_dirty"
#: Marker meaning "every entry may be affected" (group or permission rows changed).
_ALL = object()


class CachedUser(NamedTuple):
    """A cached user together with its permission codenames (``None`` = unrestricted)."""

    user: Any
    permissions: frozenset[str] | None


class UserCache:
    """Bounded TTL cache keyed by session user id."""

    def __init__(
        self,
        ttl: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self.ttl = ttl
        self._clock = clock
        self._max_entries = max_entries
        self._entries: OrderedDict[Any, tuple[float, CachedUser]] = OrderedDict()
        _CACHES.add(self)
        _ensure_listeners()

    def get(self, key: Any) -> CachedUser | None:
        """Return the live entry for ``key``, or ``None`` when missing or expired."""
        item = self._entries.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: Any, value: CachedUser) -> None:
        """Store ``value`` for ``key`` for ``ttl`` seconds, evicting the oldest when full."""
        self._entries.pop(key, None)
        self._entries[key] = (self._clock() + self.ttl, value)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, key: Any) -> None:
        """Drop the entry for ``key`` if present."""
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Drop every entry."""
        self._entries.clear()


_CACHES: weakref.WeakSet[UserCache] = weakref.WeakSet()


def invalidate_user(user_id: Any) -> None:
    """Drop ``user_id`` from every cache in this process."""
    for cache in list(_CACHES):
        cache.invalidate(user_id)


def invalidate_all() -> None:
    """Drop every entry from every cache in this process."""
    for cache in list(_CACHES):
        cache.clear()


def _collect(session: Session, _flush_context: Any) -> None:
    """Record which cache entries this flush makes stale (applied on commit)."""
    from hyperadmin.auth.models import (  # noqa: PLC0415 - lazy: keeps auth tables unregistered on import
        Group,
        GroupPermission,
        Permission,
        User,
        UserGroup,
        UserPermission,
    )

    dirty: set[Any] = session.info.setdefault(_DIRTY_KEY, set())
    for obj in (*session.new, *session.dirty, *session.deleted):
        if isinstance(obj, User):
            dirty.add(obj.id)
        elif isinstance(obj, UserGroup | UserPermission):
            dirty.add(obj.user_id)
        elif isinstance(obj, Group | GroupPermission | Permission):
            dirty.add(_ALL)


def _apply(session: Session) -> None:
    dirty = session.info.pop(_DIRTY_KEY, None)
    if not dirty:
        return
    if _ALL in dirty:
        invalidate_all()
        return
    for user_id in dirty:
        invalidate_user(user_id)


def _discard(session: Session) -> None:
    session.info.pop(_DIRTY_KEY, None)


_listening = False


def _ensure_listeners() -> None:
    """Install the write hooks once, when the first cache is built.

    Done lazily so importing the auth middleware stays free of side effects.
    """
    global _listening  # noqa: PLW0603
    if _listening:
        return
    event.listen(Session, "after_flush", _collect)
    event.listen(Session, "after_commit", _apply)
    event.listen(Session, "after_rollback", _discard)
    _listening = True
