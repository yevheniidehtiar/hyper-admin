"""Unit tests for the bring-your-own-auth bridge primitives (st-v058-byoa-25, SDD B.3).

``build_admin_dependency`` integration scenarios (requiring a real FastAPI
request) live in ``test_auth_bridge_dependency.py``.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from hyperadmin.auth.bridge import (
    BridgeDefaultPermissionChecker,
    CallablePermissionChecker,
    ExternalAuth,
    TokenCookie,
    default_can_access,
    default_display_name,
    default_user_key,
)
from hyperadmin.core.auth import PermissionChecker


class _HostUser:
    def __init__(self, **attrs: object) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)


class TestCallablePermissionChecker:
    pytestmark = pytest.mark.anyio

    async def test_callable_checker_returns_sync_lambda_result(self) -> None:
        """
        Scenario: callable checker
          Given a sync lambda has_permission
          When  CallablePermissionChecker.has_permission is awaited
          Then  the lambda's result is returned
        """
        checker = CallablePermissionChecker(lambda user, codename: codename == "view_order")

        assert await checker.has_permission(_HostUser(), "view_order") is True
        assert await checker.has_permission(_HostUser(), "delete_order") is False

    async def test_callable_checker_awaits_an_async_callable(self) -> None:
        """
        Scenario: callable checker with an async callable
          Given an async has_permission callable
          When  CallablePermissionChecker.has_permission is awaited
          Then  the callable's awaited result is returned
        """

        async def has_permission(user: object, codename: str) -> bool:
            return codename == "change_order"

        checker = CallablePermissionChecker(has_permission)

        assert await checker.has_permission(_HostUser(), "change_order") is True
        assert await checker.has_permission(_HostUser(), "delete_order") is False

    async def test_callable_checker_satisfies_the_permission_checker_protocol(self) -> None:
        """
        Scenario: callable checker satisfies PermissionChecker
          Given a CallablePermissionChecker
          When  it is checked against the PermissionChecker protocol
          Then  it is recognised as one, with an empty get_user_permissions
        """
        checker = CallablePermissionChecker(lambda user, codename: True)

        assert isinstance(checker, PermissionChecker)
        assert await checker.get_user_permissions(_HostUser()) == set()


class TestDefaultCanAccess:
    def test_default_can_access_denies_non_staff(self) -> None:
        """
        Scenario: default can_access denies non-staff
          Given a host user without is_staff or is_superuser
          When  default_can_access runs
          Then  False is returned
        """
        assert default_can_access(_HostUser()) is False
        assert default_can_access(_HostUser(is_staff=False, is_superuser=False)) is False

    def test_default_can_access_admits_staff_or_superuser(self) -> None:
        """
        Scenario: default can_access admits staff or superuser
          Given a host user with is_staff or is_superuser truthy
          When  default_can_access runs
          Then  True is returned
        """
        assert default_can_access(_HostUser(is_staff=True)) is True
        assert default_can_access(_HostUser(is_superuser=True)) is True


class TestDefaultDisplayName:
    def test_prefers_username_then_email_then_name(self) -> None:
        """
        Scenario: default display name prefers username, then email, then name
          Given a host user with username, email or name set
          When  default_display_name runs
          Then  the first of username/email/name that is truthy is returned
        """
        assert default_display_name(_HostUser(username="alice")) == "alice"
        assert default_display_name(_HostUser(email="alice@example.com")) == "alice@example.com"
        assert default_display_name(_HostUser(name="Alice")) == "Alice"

    def test_falls_back_to_str_of_the_user_when_str_is_overridden(self) -> None:
        """
        Scenario: default display name falls back to str() for an overridden __str__
          Given a host user with none of username/email/name, but an overridden __str__
          When  default_display_name runs
          Then  str(user) is returned
        """

        class _Anon:
            def __str__(self) -> str:
                return "anon-user"

        assert default_display_name(_Anon()) == "anon-user"

    def test_never_calls_str_on_an_unoverridden_pydantic_model(self) -> None:
        """
        Scenario: default display name never leaks a pydantic model's fields
          Given a pydantic host user with no username/email/name and no __str__ override
          When  default_display_name runs
          Then  the result is a safe "ClassName (pk)" label, never str(user)

        pydantic's default ``__str__`` prints every field, secrets included
        (hashed passwords, API tokens, MFA secrets). ``request.state.user_display``
        is destined for the navbar and log lines, so it must never contain that.
        """
        from pydantic import BaseModel

        class _PydanticHostUser(BaseModel):
            id: int
            hashed_password: str

        user = _PydanticHostUser(id=7, hashed_password="super-secret")

        result = default_display_name(user)

        assert "super-secret" not in result
        assert result == "_PydanticHostUser (7)"


class TestDefaultUserKey:
    def test_returns_the_users_id_attribute(self) -> None:
        """
        Scenario: default user_key returns the id attribute
          Given a host user with an id
          When  default_user_key runs
          Then  that id is returned
        """
        assert default_user_key(_HostUser(id=42)) == 42

    def test_raises_type_error_without_an_id_attribute(self) -> None:
        """
        Scenario: default user_key rejects a user with no id
          Given a host user with no id attribute
          When  default_user_key runs
          Then  a TypeError is raised instead of silently returning None

        A silent ``None`` would make every such user share the same
        ``request.state.user_key``, merging per-user keyed state (presence,
        audit, rate limits) across users.
        """
        with pytest.raises(TypeError, match="user_key"):
            default_user_key(_HostUser())


class TestBridgeDefaultPermissionChecker:
    pytestmark = pytest.mark.anyio

    async def test_superuser_has_every_permission(self) -> None:
        """
        Scenario: default checker grants superusers everything
          Given BridgeDefaultPermissionChecker with no allow_full_access
          When  has_permission is awaited for a superuser on a non-view codename
          Then  True is returned
        """
        checker = BridgeDefaultPermissionChecker()

        assert await checker.has_permission(_HostUser(is_superuser=True), "delete_order") is True

    async def test_non_superuser_gets_view_only(self) -> None:
        """
        Scenario: default checker is view-only for everyone else
          Given BridgeDefaultPermissionChecker with no allow_full_access
          When  has_permission is awaited for a non-superuser
          Then  only view_* codenames return True
        """
        checker = BridgeDefaultPermissionChecker()
        staff = _HostUser(is_superuser=False, is_staff=True)

        assert await checker.has_permission(staff, "view_order") is True
        assert await checker.has_permission(staff, "change_order") is False
        assert await checker.has_permission(staff, "delete_order") is False
        assert await checker.has_permission(staff, "add_order") is False

    async def test_allow_full_access_grants_everyone_everything(self) -> None:
        """
        Scenario: allow_full_access restores full access for anyone who passed can_access
          Given BridgeDefaultPermissionChecker(allow_full_access=True)
          When  has_permission is awaited for a non-superuser
          Then  True is returned for a non-view codename too
        """
        checker = BridgeDefaultPermissionChecker(allow_full_access=True)
        staff = _HostUser(is_superuser=False)

        assert await checker.has_permission(staff, "delete_order") is True

    async def test_allow_full_access_still_denies_change_on_the_protected_model(self) -> None:
        """
        Scenario: allow_full_access never lets a non-superuser escalate via the host user model
          Given BridgeDefaultPermissionChecker(allow_full_access=True, protected_model="user")
          When  has_permission is awaited for a non-superuser on change_user/delete_user
          Then  False is returned, even though allow_full_access grants every other codename

        Without this guard, a staff user granted ``allow_full_access`` could
        edit their own ``is_superuser`` flag through the host user model (SDD
        section B.3, item 3; Owner decision 3). The checker cannot name the
        host user model on its own, so a host that enables
        ``allow_full_access`` must pass ``protected_model`` for this guard to
        apply.
        """
        checker = BridgeDefaultPermissionChecker(allow_full_access=True, protected_model="user")
        staff = _HostUser(is_superuser=False)

        assert await checker.has_permission(staff, "change_user") is False
        assert await checker.has_permission(staff, "delete_user") is False
        # Every other model, and view_* on the protected model, still works.
        assert await checker.has_permission(staff, "delete_order") is True
        assert await checker.has_permission(staff, "view_user") is True

    async def test_allow_full_access_protected_model_match_is_case_insensitive(self) -> None:
        """
        Scenario: protected_model matching ignores codename case
          Given BridgeDefaultPermissionChecker(allow_full_access=True, protected_model="User")
          When  has_permission is awaited for a non-superuser on change_user
          Then  False is returned regardless of the casing used for either value
        """
        checker = BridgeDefaultPermissionChecker(allow_full_access=True, protected_model="User")
        staff = _HostUser(is_superuser=False)

        assert await checker.has_permission(staff, "change_User") is False

    async def test_superuser_bypasses_the_protected_model_guard(self) -> None:
        """
        Scenario: a superuser is unaffected by protected_model
          Given BridgeDefaultPermissionChecker(protected_model="user")
          When  has_permission is awaited for a superuser on change_user
          Then  True is returned
        """
        checker = BridgeDefaultPermissionChecker(protected_model="user")

        assert await checker.has_permission(_HostUser(is_superuser=True), "change_user") is True

    async def test_satisfies_the_permission_checker_protocol(self) -> None:
        """
        Scenario: default checker satisfies PermissionChecker
          Given a BridgeDefaultPermissionChecker
          When  it is checked against the PermissionChecker protocol
          Then  it is recognised as one, with an empty get_user_permissions
        """
        checker = BridgeDefaultPermissionChecker()

        assert isinstance(checker, PermissionChecker)
        assert await checker.get_user_permissions(_HostUser()) == set()


class TestExternalAuthDefaults:
    def test_only_get_user_is_required(self) -> None:
        """
        Scenario: ExternalAuth needs only get_user
          Given ExternalAuth is constructed with only get_user
          When  its other fields are read
          Then  every other field holds its documented fail-safe default
        """

        def get_user() -> None:
            return None

        auth = ExternalAuth(get_user=get_user)

        assert auth.get_user is get_user
        assert auth.can_access is default_can_access
        assert auth.has_permission is None
        assert auth.login_url is None
        assert auth.logout_url is None
        assert auth.next_param == "next"
        assert auth.display_name is default_display_name
        assert auth.user_key is default_user_key
        assert auth.token_cookie is None
        assert auth.websocket_user is None
        assert auth.allow_full_access is False

    def test_is_frozen(self) -> None:
        auth = ExternalAuth(get_user=lambda: None)

        with pytest.raises(AttributeError):
            auth.login_url = "/login"  # type: ignore[misc]

    def test_get_user_is_keyword_only(self) -> None:
        with pytest.raises(TypeError):
            ExternalAuth(lambda: None)  # type: ignore[misc,call-arg]


class TestTokenCookieDefaults:
    def test_defaults(self) -> None:
        """
        Scenario: TokenCookie defaults
          Given TokenCookie is constructed with no arguments
          When  its fields are read
          Then  every field holds its documented default
        """
        cookie = TokenCookie()

        assert cookie.name == "hyperadmin_token"
        assert cookie.scheme == "Bearer"
        assert cookie.max_age == 8 * 3600
        assert cookie.handoff_path == "/auth/session"
        assert cookie.token_endpoint is None

    def test_is_frozen(self) -> None:
        cookie = TokenCookie()

        with pytest.raises(AttributeError):
            cookie.name = "other"  # type: ignore[misc]

    def test_token_endpoint_accepts_a_url_string(self) -> None:
        cookie = TokenCookie(token_endpoint="/token")

        assert cookie.token_endpoint == "/token"

    def test_token_endpoint_accepts_a_callable(self) -> None:
        async def issue_token(username: str, password: str) -> str | None:
            return "jwt"

        cookie = TokenCookie(token_endpoint=issue_token)

        assert cookie.token_endpoint is issue_token


def _run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_importing_bridge_registers_no_hyperadmin_tables() -> None:
    """``auth/bridge.py`` must not import ``auth/models.py`` (SDD section B.5).

    Run in a subprocess: table registration on ``SQLModel.metadata`` is
    process-global, so a prior test importing the models would otherwise
    contaminate this one.
    """
    out = _run(
        """
        import hyperadmin.auth.bridge
        from sqlmodel import SQLModel
        print(sorted(t for t in SQLModel.metadata.tables if t.startswith("hyperadmin_")))
        """
    )
    assert out == "[]"


def test_bridge_symbols_resolve_through_the_lazy_auth_package() -> None:
    """``from hyperadmin.auth import ExternalAuth`` works without importing auth/models.py."""
    out = _run(
        """
        from hyperadmin.auth import (
            BridgeDefaultPermissionChecker,
            CallablePermissionChecker,
            ExternalAuth,
            TokenCookie,
            build_admin_dependency,
        )
        from sqlmodel import SQLModel
        print(
            sorted(t for t in SQLModel.metadata.tables if t.startswith("hyperadmin_")),
            ExternalAuth.__name__,
            TokenCookie.__name__,
            CallablePermissionChecker.__name__,
            BridgeDefaultPermissionChecker.__name__,
            callable(build_admin_dependency),
        )
        """
    )
    assert out == (
        "[] ExternalAuth TokenCookie CallablePermissionChecker BridgeDefaultPermissionChecker True"
    )
