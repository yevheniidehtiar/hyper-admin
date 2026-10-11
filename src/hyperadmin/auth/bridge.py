"""Bring-your-own-auth bridge.

Lets a host FastAPI application plug its own authentication and permission
model into HyperAdmin, without the built-in ``hyperadmin_*`` user, group and
permission tables. A host wires this in with::

    from hyperadmin.auth import ExternalAuth

    admin = Admin(app, auth=ExternalAuth(get_user=get_current_user))

See ``docs/specs/bring-your-own-app.md`` section B.3 for the full design.

This module imports only from ``hyperadmin.core`` (CONSTITUTION.md §1, §2). It
MUST NOT import ``hyperadmin.auth.models`` — doing so would register the
built-in ``hyperadmin_*`` tables on ``SQLModel.metadata`` for every host that
merely imports this module, which bridge-mode hosts never want
(``test_auth_bridge.py`` checks this in a subprocess).
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

from fastapi import Depends, Request

from hyperadmin.core.auth import AdminAccessDenied, AdminAuthenticationRequired
from hyperadmin.core.display import get_display_name

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from hyperadmin.core.auth import PermissionChecker

_T = TypeVar("_T")

#: A value, or an awaitable resolving to one — ``get_user``, ``can_access``,
#: ``has_permission`` and ``TokenCookie.token_endpoint`` may each be a plain
#: sync function or an ``async def``. ``display_name`` and ``user_key`` are
#: called without awaiting (:func:`build_admin_dependency`), so they must stay
#: sync: an async ``display_name`` would leave an unawaited coroutine in
#: ``request.state.user_display``.
MaybeAwaitable: TypeAlias = _T | Awaitable[_T]

__all__ = [
    "BridgeDefaultPermissionChecker",
    "CallablePermissionChecker",
    "ExternalAuth",
    "MaybeAwaitable",
    "TokenCookie",
    "build_admin_dependency",
    "default_can_access",
    "default_display_name",
    "default_user_key",
]


async def _maybe_await(value: MaybeAwaitable[_T]) -> _T:
    """Return ``value``, awaiting it first when it is awaitable.

    Normalises every bridge callable so callers never need to know whether a
    host supplied a sync function or an ``async def``.
    """
    if inspect.isawaitable(value):
        return await value
    return value  # type: ignore[return-value]


def default_can_access(user: Any) -> bool:
    """Admit a host user with a truthy ``is_superuser`` or ``is_staff``.

    The default ``ExternalAuth.can_access`` policy. A host whose user model
    has neither attribute should pass its own callable.
    """
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))


def default_display_name(user: Any) -> str:
    """Return the first of ``user.username``, ``.email`` or ``.name`` that is truthy.

    Falls back to :func:`hyperadmin.core.display.get_display_name`, never to
    plain ``str(user)``: a pydantic/SQLModel host user whose ``__str__`` is
    not overridden prints every field, secrets included (hashed passwords,
    API tokens, MFA secrets), and the result here is stored on
    ``request.state.user_display`` for the navbar and log lines.
    """
    for attr in ("username", "email", "name"):
        value = getattr(user, attr, None)
        if value:
            return str(value)
    return get_display_name(user)


def default_user_key(user: Any) -> Hashable:
    """Return ``user.id`` — the value ``request.state.user_key`` is set to.

    Raises:
        TypeError: when ``user`` has no ``id`` attribute. A silent ``None``
            would make every such user share the same
            ``request.state.user_key``, merging per-user keyed state
            (presence, audit, rate limits) across users. A host whose user
            model has no ``id`` should pass ``ExternalAuth(user_key=...)``.
    """
    try:
        return user.id
    except AttributeError:
        raise TypeError(
            f"{type(user).__name__} has no 'id' attribute for user_key; "
            "pass ExternalAuth(user_key=...) for a host user keyed differently."
        ) from None


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenCookie:
    """Bridges a bearer token into an ``HttpOnly`` cookie for bearer-only hosts.

    Opt-in: set ``ExternalAuth(token_cookie=TokenCookie())``. See
    ``docs/specs/bring-your-own-app.md`` section B.4.
    """

    name: str = "hyperadmin_token"
    scheme: str = "Bearer"
    max_age: int | None = 8 * 3600
    handoff_path: str = "/auth/session"
    #: Opt-in admin login form for bearer-only hosts (B.4): a token URL, or an
    #: ``issue_token(username, password) -> token | None`` callable.
    token_endpoint: str | Callable[[str, str], MaybeAwaitable[str | None]] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalAuth:
    """Bring-your-own-auth configuration for ``Admin(auth=...)``.

    Only ``get_user`` is required. Every other field has a fail-safe default;
    see ``docs/specs/bring-your-own-app.md`` section B.3.
    """

    #: Any FastAPI dependency resolving the current host user, or ``None`` for
    #: an anonymous request. Resolved as a sub-dependency of
    #: :func:`build_admin_dependency`, so host overrides, ``yield`` dependencies
    #: and ``request.app.state`` reads all work normally.
    get_user: Callable[..., Any]
    can_access: Callable[[Any], MaybeAwaitable[bool]] = default_can_access
    has_permission: Callable[[Any, str], MaybeAwaitable[bool]] | PermissionChecker | None = None
    login_url: str | None = None
    logout_url: str | None = None
    next_param: str = "next"
    display_name: Callable[[Any], str] = default_display_name
    user_key: Callable[[Any], Hashable] = default_user_key
    token_cookie: TokenCookie | None = None
    websocket_user: Callable[[WebSocket], Awaitable[Any | None]] | None = None
    #: Without ``has_permission``: ``False`` (default) means the fail-safe
    #: default grants a superuser everything and everyone else ``view_*`` only.
    #: ``True`` grants every permission to anyone who already passed
    #: ``can_access``. See :class:`BridgeDefaultPermissionChecker`.
    allow_full_access: bool = False


class CallablePermissionChecker:
    """Adapts a plain ``has_permission(user, codename)`` callable to a permission checker.

    Satisfies ``core.auth.PermissionChecker``. ``fn`` may be a sync or async
    callable (SDD section B.3, item 2).
    """

    __slots__ = ("_fn",)

    def __init__(self, fn: Callable[[Any, str], MaybeAwaitable[bool]]) -> None:
        self._fn = fn

    async def has_permission(self, user: Any, codename: str) -> bool:
        """Return the wrapped callable's result, awaited if it returned one."""
        return bool(await _maybe_await(self._fn(user, codename)))

    async def get_user_permissions(self, user: Any) -> set[str]:  # noqa: ARG002
        """Not derivable from a single ``has_permission`` callable; always empty.

        Warning:
            This empty set is not "no permissions" — it is "cannot enumerate
            them". A wiring story that fills ``request.state.user_permissions``
            from this method would hide every model from a superuser's
            sidebar (see ``_sidebar.html``, which treats an empty set as
            "show nothing"). In bridge mode, ``request.state.user_permissions``
            must stay unset; permission checks must go through
            ``has_permission`` instead.
        """
        return set()


class BridgeDefaultPermissionChecker:
    """Fail-safe permission checker used when ``ExternalAuth.has_permission`` is unset.

    A superuser (``user.is_superuser`` truthy) holds every permission. Every
    other user holds only ``view_*`` permissions — never ``change_*``,
    ``add_*`` or ``delete_*`` on anything, including the host user model. This
    stops a non-superuser staff user from granting themselves a superuser flag
    (SDD section B.3, item 3; Owner decision 3).

    That protection holds by default, but ``allow_full_access=True`` (Owner
    decision 3's documented opt-in) grants every codename, including
    ``change_<hostuser>``, to anyone who passed ``can_access`` — which
    reopens the same privilege-escalation path unless ``protected_model`` is
    also passed.

    Args:
        allow_full_access: Mirrors ``ExternalAuth.allow_full_access``. When
            ``True``, every permission is granted to any user who already
            passed ``can_access`` — not just superusers.
        protected_model: The host user model's lowercased class name (e.g.
            ``"user"``). When set, a non-superuser is denied ``change_*`` and
            ``delete_*`` on this model even under ``allow_full_access`` — this
            is the guard that stops a staff user from granting themselves
            ``is_superuser`` through the admin. The checker has no way to
            know the host user model on its own, so a host that passes
            ``allow_full_access=True`` should also pass ``protected_model``
            (typically wired in by ``Admin.__init__`` from its own knowledge
            of the host user model).
    """

    __slots__ = ("_allow_full_access", "_protected_model")

    def __init__(
        self,
        *,
        allow_full_access: bool = False,
        protected_model: str | None = None,
    ) -> None:
        self._allow_full_access = allow_full_access
        self._protected_model = protected_model.lower() if protected_model else None

    async def has_permission(self, user: Any, codename: str) -> bool:
        if not getattr(user, "is_superuser", False) and self._protected_model is not None:
            for prefix in ("change_", "delete_"):
                if codename.lower() == f"{prefix}{self._protected_model}":
                    return False
        if self._allow_full_access or getattr(user, "is_superuser", False):
            return True
        return codename.startswith("view_")

    async def get_user_permissions(self, user: Any) -> set[str]:  # noqa: ARG002
        """Not derivable from the fail-safe policy; always empty.

        Warning:
            Same caveat as :meth:`CallablePermissionChecker.get_user_permissions`:
            this empty set must never be assigned to
            ``request.state.user_permissions`` — it would hide every model
            from a superuser's sidebar, which treats an empty set as "show
            nothing" (see ``_sidebar.html``). Permission checks in bridge mode
            must go through :meth:`has_permission`.
        """
        return set()


def build_admin_dependency(auth: ExternalAuth) -> Callable[..., Awaitable[Any]]:
    """Build the FastAPI dependency that resolves and validates the admin principal.

    The returned callable declares ``auth.get_user`` as its own sub-dependency
    (``Depends(auth.get_user)``) rather than calling it directly, so FastAPI
    resolves it the normal way: ``app.dependency_overrides``, nested
    sub-dependencies, dependencies that ``yield``, sync functions, and
    dependencies reading ``request.app.state`` all behave exactly as they
    would on any other host route (SDD section B.1).

    On success, sets ``request.state.user``, ``.user_key`` and
    ``.user_display`` and returns the host user.

    Raises:
        AdminAuthenticationRequired: when the host dependency resolves no user
            (``None``).
        AdminAccessDenied: when ``auth.can_access(user)`` returns a falsy
            value.
    """

    async def _resolve_admin_user(
        request: Request,
        user: Any = Depends(auth.get_user),  # noqa: B008 - FastAPI's own DI idiom (SDD B.1)
    ) -> Any:
        if user is None:
            raise AdminAuthenticationRequired
        if not await _maybe_await(auth.can_access(user)):
            raise AdminAccessDenied
        request.state.user = user
        request.state.user_key = auth.user_key(user)
        request.state.user_display = auth.display_name(user)
        return user

    return _resolve_admin_user
