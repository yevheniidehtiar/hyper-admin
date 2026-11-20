"""What the plugin reads from the ``Admin`` object: its sessions and its permission checker.

The report routes and the dashboard widgets share these helpers, so both apply
the same rule: a codename is checked through the checker the admin hands to its
model views, and without auth everything is open, as model views are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession
    from starlette.requests import Request


def permission_checker(admin: Any) -> Any:
    """The checker admin model views use: none unless the admin has auth configured."""
    if getattr(admin, "auth", None) is None and getattr(admin, "auth_backend", None) is None:
        return None
    return admin.permission_checker


def session_source(admin: Any) -> Callable[[], AsyncSession]:
    """The host's session factory when it gave one, else a session maker on the admin engine."""
    if admin.session_factory is not None:
        return admin.session_factory
    return async_sessionmaker(admin.engine, expire_on_commit=False)


async def has_permission(admin: Any, request: Request, codename: str | None) -> bool:
    """Whether the request's user holds ``codename`` (``None``: nothing to hold).

    Raises:
        HTTPException: 403 when auth is configured and the request has no user.
    """
    checker = permission_checker(admin)
    if codename is None or checker is None:
        return True
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=403, detail="Authentication required")
    return bool(await checker.has_permission(user, codename))
