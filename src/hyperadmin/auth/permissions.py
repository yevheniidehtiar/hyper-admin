"""Permission checking and auto-registration services.

Implements ``PermissionChecker`` and ``PermissionRegistry`` protocols.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import select

from hyperadmin.auth.models import (
    Group,
    GroupPermission,
    Permission,
    User,
    UserGroup,
    UserPermission,
)

_ACTIONS = ("view", "add", "change", "delete")


def generate_default_permissions(model_name: str) -> list[tuple[str, str]]:
    """Return the 4 default (codename, human_name) tuples for a model."""
    name = model_name.lower()
    return [(f"{action}_{name}", f"Can {action} {name}") for action in _ACTIONS]


class PermissionSyncService:
    """Syncs auto-generated and custom permissions to the database on startup."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def sync_permissions(self, registered_models: list[Any]) -> None:
        """Create missing permissions for all registered models.

        Args:
            registered_models: List of ``(model_name, admin_class)`` tuples.
        """
        async with AsyncSession(self.engine) as session:
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


class ModelPermissionChecker:
    """Checks user permissions via direct grants and group inheritance."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def has_permission(self, user: User, codename: str) -> bool:
        """Return ``True`` if the user holds the given permission."""
        if user.is_superuser:
            return True
        perms = await self.get_user_permissions(user)
        return codename in perms

    async def get_user_permissions(self, user: User) -> set[str]:
        """Return the union of direct + group-inherited permission codenames."""
        async with AsyncSession(self.engine) as session:
            # Direct permissions
            stmt = (
                select(Permission.codename)
                .join(
                    UserPermission,
                    UserPermission.permission_id == Permission.id,  # type: ignore[arg-type]
                )
                .where(UserPermission.user_id == user.id)
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
                .where(UserGroup.user_id == user.id)
            )
            inherited = set((await session.execute(stmt)).scalars().all())

            return direct | inherited
