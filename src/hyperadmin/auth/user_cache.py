"""Per-worker TTL cache for the authenticated user and its permission set.

Opt-in through ``HyperAdminSettings.user_cache_ttl``. The cache lives in one
process: a write on this worker drops the affected entries at commit, while other
workers may serve a stale entry for up to the TTL (see the production notes).
"""

from __future__ import annotations

import copy
import time
import weakref
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, NamedTuple

from sqlalchemy import event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import ORMExecuteState

#: Upper bound on cached users per middleware instance; the oldest entry is evicted first.
DEFAULT_MAX_ENTRIES = 1024

_DIRTY_KEY = "hyperadmin_user_cache_dirty"
#: Marker meaning "every entry may be affected" (group or permission rows changed).
_ALL = object()


class CachedUser(NamedTuple):
    """A user snapshot with its permission codenames (``None`` = unrestricted).

    ``user`` is private to the cache: hand out :func:`clone_user` copies, never this
    object, so no request can change what another one is served.
    """

    user: Any
    permissions: frozenset[str] | None


def clone_user(user: Any) -> Any | None:
    """Return a fresh detached copy of a mapped ``user``'s loaded columns.

    ``None`` when ``user`` is not an ORM instance (it is then not cacheable). The copy
    is transient with no pending changes; relationships stay empty.
    """
    state = sa_inspect(user, raiseerr=False)
    if state is None:
        return None
    mapper = state.mapper
    clone = mapper.class_manager.new_instance()
    for attr in mapper.column_attrs:
        if attr.key in state.dict:
            set_committed_value(clone, attr.key, copy.copy(state.dict[attr.key]))
    return clone


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
        self._generation = 0
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

    @property
    def generation(self) -> int:
        """Counter bumped by every invalidation; read it before loading a value to cache."""
        return self._generation

    def set(self, key: Any, value: CachedUser, generation: int) -> None:
        """Store ``value`` for ``key`` for ``ttl`` seconds, evicting the oldest when full.

        ``generation`` is the :attr:`generation` read before ``value`` was loaded. When an
        invalidation ran since, the value may predate a committed write and is dropped.
        """
        if generation != self._generation:
            return
        self._entries.pop(key, None)
        self._entries[key] = (self._clock() + self.ttl, value)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, key: Any) -> None:
        """Drop the entry for ``key`` if present, and veto fills that started earlier."""
        self._generation += 1
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Drop every entry, and veto fills that started earlier."""
        self._generation += 1
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
        owner: Any
        if isinstance(obj, User):
            owner = obj.id
        elif isinstance(obj, UserGroup | UserPermission):
            owner = obj.user_id
        elif isinstance(obj, Group | GroupPermission | Permission):
            owner = _ALL
        else:
            continue
        if owner is not None:  # a brand-new user has no id yet and no entry to drop
            dirty.add(owner)


def _auth_table_names() -> frozenset[str]:
    from hyperadmin.auth.models import (  # noqa: PLC0415 - lazy: keeps auth tables unregistered on import
        Group,
        GroupPermission,
        Permission,
        User,
        UserGroup,
        UserPermission,
    )

    models = (User, Group, Permission, UserGroup, UserPermission, GroupPermission)
    return frozenset(model.__table__.name for model in models)  # type: ignore[union-attr]


def _collect_bulk(state: ORMExecuteState) -> None:
    """Treat a bulk INSERT/UPDATE/DELETE on an auth table as touching every entry.

    These statements skip the unit of work, so ``_collect`` never sees them.
    """
    if not (state.is_insert or state.is_update or state.is_delete):
        return
    table = getattr(state.statement, "table", None)
    if getattr(table, "name", None) in _auth_table_names():
        state.session.info.setdefault(_DIRTY_KEY, set()).add(_ALL)


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
    event.listen(Session, "do_orm_execute", _collect_bulk)
    event.listen(Session, "after_commit", _apply)
    event.listen(Session, "after_rollback", _discard)
    _listening = True
