"""Authentication and authorization protocol definitions.

These protocols define the injection seams for auth services. Concrete
implementations live in ``hyperadmin.auth``, keeping ``core/`` free of
ORM and HTTP dependencies.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from starlette.requests import Request


@runtime_checkable
class AuthBackend(Protocol):
    """Authenticates users and manages login/logout sessions."""

    async def authenticate(self, username: str, password: str) -> Any | None: ...

    async def login(self, request: Request, user: Any) -> None: ...

    async def logout(self, request: Request) -> None: ...


@runtime_checkable
class CurrentUserProvider(Protocol):
    """Resolves the current user from an incoming request."""

    async def get_current_user(self, request: Request) -> Any | None: ...


@runtime_checkable
class PermissionChecker(Protocol):
    """Checks whether a user holds a specific permission."""

    async def has_permission(self, user: Any, codename: str) -> bool: ...

    async def get_user_permissions(self, user: Any) -> set[str]: ...


@runtime_checkable
class PermissionRegistry(Protocol):
    """Syncs auto-generated and custom permissions to the database."""

    async def sync_permissions(self, registered_models: list[Any]) -> None: ...
