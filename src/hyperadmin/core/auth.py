"""Authentication and authorization protocol definitions.

These protocols define the injection seams for auth services. Concrete
implementations live in ``hyperadmin.auth``, keeping ``core/`` free of
ORM and HTTP dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from starlette.requests import Request


class AdminAuthenticationRequired(Exception):
    """Raised when an admin request has no authenticated principal.

    The admin route class turns it into a login redirect (browser), a 401 with
    ``HX-Redirect``/``HX-Refresh`` (HTMX) or a plain 401 (API).
    """

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AdminAccessDenied(Exception):
    """Raised when an authenticated principal may not access the admin at all.

    Model and object permission failures stay ``HTTPException(403)``; this is the
    admin-wide ``can_access`` denial.
    """

    def __init__(self, message: str = "Admin access denied") -> None:
        super().__init__(message)


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


@runtime_checkable
class ObjectPermissionChecker(Protocol):
    """Checks whether a user may perform ``action`` on a specific object.

    Complements :class:`PermissionChecker` (model-level) with per-object
    authorization. ``action`` shares the model-level codenames:
    ``"view"``, ``"add"``, ``"change"``, ``"delete"``. Implementations may
    accept additional custom action codenames.

    Superuser bypass and other policy decisions are the responsibility of
    the concrete implementation, not the protocol.
    """

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool: ...


class DefaultObjectPermissionChecker:
    """Permissive default: allow every action on every object.

    Acts as the no-op fallback when an application has not configured a
    custom :class:`ObjectPermissionChecker`. Existing model-level
    :class:`PermissionChecker` enforcement is unaffected.
    """

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return True
