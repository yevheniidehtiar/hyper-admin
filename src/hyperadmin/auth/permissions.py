"""Permission checking and auto-registration services.

Implements ``PermissionChecker`` and ``PermissionRegistry`` protocols.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import InstanceState
from sqlmodel import select

from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)
from hyperadmin.core.adapters import open_session, require_engine_or_session_factory

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractAsyncContextManager

    from sqlalchemy.ext.asyncio import AsyncEngine

    from hyperadmin.core.adapters import AsyncSessionLike, SessionFactory

_ACTIONS = ("view", "add", "change", "delete")

#: Key in the user instance's SQLAlchemy ``InstanceState.info`` holding its resolved set.
_RESOLVED_KEY = "hyperadmin_permissions"


def _resolved_store(user: Any) -> dict[Any, Any] | None:
    """Return the per-instance dict the resolved set lives in, or ``None`` if unmapped.

    The auth backend builds a new user object for every request, so what is stored here
    ends with the request. A user that is not an ORM instance gets no store: nothing
    says how long such an object lives, so its permissions are read on every check.
    """
    state = sa_inspect(user, raiseerr=False)
    if not isinstance(state, InstanceState):
        return None
    info: dict[Any, Any] = state.info
    return info


def forget_user_permissions(user: Any) -> None:
    """Drop the permission set remembered on ``user``; the next check reads it again.

    Call it after a write that may change what this user object holds while the object
    is still in use (the permissions matrix does, after a save).
    """
    store = _resolved_store(user)
    if store is not None:
        store.pop(_RESOLVED_KEY, None)


def generate_default_permissions(model_name: str) -> list[tuple[str, str]]:
    """Return the 4 default (codename, human_name) tuples for a model."""
    name = model_name.lower()
    return [(f"{action}_{name}", f"Can {action} {name}") for action in _ACTIONS]


class PermissionSyncService:
    """Syncs auto-generated and custom permissions to the database on startup."""

    def __init__(
        self, engine: AsyncEngine | None = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("PermissionSyncService", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given."""
        return open_session(self.engine, self.session_factory)

    async def sync_permissions(self, registered_models: list[Any]) -> None:
        """Create missing permissions for all registered models.

        Args:
            registered_models: List of ``(model_name, admin_class)`` tuples.
        """
        async with self._session() as session:
            existing = (await session.execute(select(Permission.codename))).scalars().all()
            existing_set = set(existing)

            to_create: list[Permission] = []
            for model_name, admin_class in registered_models:
                # Default CRUD permissions
                for codename, name in generate_default_permissions(model_name):
                    if codename not in existing_set:
                        to_create.append(
                            Permission(codename=codename, name=name, content_type=model_name)
                        )
                        existing_set.add(codename)

                # Custom permissions from ModelAdmin.permissions
                custom = getattr(admin_class, "permissions", None) or []
                for codename, name in custom:
                    if codename not in existing_set:
                        to_create.append(
                            Permission(codename=codename, name=name, content_type=model_name)
                        )
                        existing_set.add(codename)

            if to_create:
                session.add_all(to_create)
                await session.commit()

    async def sync_codenames(self, permissions: Iterable[tuple[str, str, str | None]]) -> None:
        """Create missing permissions that belong to no model (e.g. plugin codenames).

        Args:
            permissions: ``(codename, name, content_type)`` tuples; existing
                codenames are left untouched.
        """
        async with self._session() as session:
            existing = set((await session.execute(select(Permission.codename))).scalars().all())
            to_create: list[Permission] = []
            for codename, name, content_type in permissions:
                if codename not in existing:
                    to_create.append(
                        Permission(codename=codename, name=name, content_type=content_type)
                    )
                    existing.add(codename)
            if to_create:
                session.add_all(to_create)
                await session.commit()


class ModelPermissionChecker:
    """Checks user permissions via direct grants and group inheritance."""

    def __init__(
        self, engine: AsyncEngine | None = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory("ModelPermissionChecker", engine, session_factory)
        self.engine = engine
        self.session_factory = session_factory

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given."""
        return open_session(self.engine, self.session_factory)

    async def has_permission(self, user: User, codename: str) -> bool:
        """Return ``True`` if the user holds the given permission."""
        if user.is_superuser:
            return True
        return codename in await self._resolve(user)

    async def get_user_permissions(self, user: User) -> set[str]:
        """Return the union of direct + group-inherited permission codenames.

        The set is read once per user object and remembered on it, so every later check
        for the same object (one request) costs no query. The caller gets its own copy.
        """
        return set(await self._resolve(user))

    async def _resolve(self, user: User) -> frozenset[str]:
        """Return the user's permission set, reading it at most once per user object."""
        store = _resolved_store(user)
        # Keyed by checker too, so two checkers on different databases never share a set.
        resolved = store.get(_RESOLVED_KEY) if store is not None else None
        if resolved is not None and resolved[0] is self:
            permissions: frozenset[str] = resolved[1]
            return permissions
        permissions = await self._load(user.id)
        if store is not None:
            store[_RESOLVED_KEY] = (self, permissions)
        return permissions

    async def _load(self, user_id: Any) -> frozenset[str]:
        """Read direct and group-inherited codenames in one session (two statements)."""
        async with self._session() as session:
            # Direct permissions
            stmt = (
                select(Permission.codename)
                .join(
                    UserPermission,
                    UserPermission.permission_id == Permission.id,  # type: ignore[arg-type]
                )
                .where(UserPermission.user_id == user_id)
            )
            direct = set((await session.execute(stmt)).scalars().all())

            # Group-inherited permissions
            stmt = (
                select(Permission.codename)
                .join(
                    GroupPermission,
                    GroupPermission.permission_id == Permission.id,  # type: ignore[arg-type]
                )
                .join(Group, Group.id == GroupPermission.group_id)  # type: ignore[arg-type]
                .join(UserGroup, UserGroup.group_id == Group.id)  # type: ignore[arg-type]
                .where(UserGroup.user_id == user_id)
            )
            inherited = set((await session.execute(stmt)).scalars().all())

            return frozenset(direct | inherited)
