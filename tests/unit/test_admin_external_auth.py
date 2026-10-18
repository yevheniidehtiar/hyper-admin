"""``Admin(auth=ExternalAuth(...))`` wiring (st-v058-byoa-40, SDD B.3).

The bridge is exercised end to end: a host ``get_user`` dependency reading a
bearer token, a real admin mounted at ``/admin`` over SQLite, and the admin's
own views, permission checks and route class.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.bridge import (
    BridgeDefaultPermissionChecker,
    CallablePermissionChecker,
    ExternalAuth,
    HostUserModelGuard,
    TokenCookie,
)
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.realtime import RealtimeSettings
from hyperadmin.realtime.ws import WS_CLOSE_UNAUTHORIZED

_SECRET = "bridge-test-secret"


# ---------------------------------------------------------------------------
# Host models and the host's own auth
# ---------------------------------------------------------------------------


class BxHostUser(SQLModel, table=True):
    """The host application's own user model (not ``hyperadmin_users``)."""

    __tablename__ = "bx_host_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    full_name: str = ""
    is_staff: bool = False
    is_superuser: bool = False


class BxOrder(SQLModel, table=True):
    __tablename__ = "bx_order"

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int | None = None
    status: str = "new"


class BxHostUserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class BxOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


STAFF = BxHostUser(id=1, username="ada", full_name="Ada Lovelace", is_staff=True)
SUPER = BxHostUser(id=2, username="root", full_name="Root", is_staff=True, is_superuser=True)
CUSTOMER = BxHostUser(id=3, username="cus", full_name="Customer")
_TOKENS = {"staff-token": STAFF, "super-token": SUPER, "customer-token": CUSTOMER}


def get_current_user(authorization: str | None = Header(default=None)) -> BxHostUser | None:
    """The host's ``get_user``: resolves a bearer token, ``None`` when anonymous."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return _TOKENS.get(authorization.removeprefix("Bearer "))


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class _OwnerOnly:
    """Object checker recording the user it was called with."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        self.calls.append(user)
        return obj.owner_id == user.id


class _NamedChecker:
    """A ``PermissionChecker`` object (not a plain callable)."""

    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed

    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in self.allowed

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.allowed)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bridge.db'}")

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                SQLModel.metadata.create_all,
                tables=[BxHostUser.__table__, BxOrder.__table__],  # type: ignore[attr-defined]
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for user in (STAFF, SUPER, CUSTOMER):
                session.add(BxHostUser(**user.model_dump()))
            session.add(BxOrder(id=5, owner_id=1))
            session.add(BxOrder(id=42, owner_id=1))
            session.add(BxOrder(id=43, owner_id=2))
            await session.commit()

    anyio.run(_seed)
    return engine


def _settings(**overrides: Any) -> HyperAdminSettings:
    values: dict[str, Any] = {"secret_key": _SECRET, "csrf_mode": "off", **overrides}
    return HyperAdminSettings(**values)


def _register(object_checker: Any = None) -> None:
    site.register(BxHostUser, BxHostUserAdmin)
    site.register(
        BxOrder, BxOrderAdmin, options=AdminOptions(object_permission_checker=object_checker)
    )


def _build(
    engine: AsyncEngine,
    *,
    object_checker: Any = None,
    settings: HyperAdminSettings | None = None,
    mount_mode: str | None = None,
    **auth_kwargs: Any,
) -> tuple[Admin, TestClient]:
    app = FastAPI()
    _register(object_checker)
    settings = settings or _settings()
    if mount_mode is not None:
        settings.mount_mode = mount_mode  # type: ignore[assignment]
    admin = Admin(
        app,
        engine=engine,
        settings=settings,
        auth=ExternalAuth(get_user=get_current_user, **auth_kwargs),
    )
    admin.mount("/admin")
    return admin, TestClient(app, follow_redirects=False)


async def _order_exists(engine: AsyncEngine, order_id: int) -> bool:
    async with AsyncSession(engine) as session:
        return await session.get(BxOrder, order_id) is not None


async def _is_superuser(engine: AsyncEngine, user_id: int) -> bool:
    async with AsyncSession(engine) as session:
        user = await session.get(BxHostUser, user_id)
        assert user is not None
        return user.is_superuser


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_staff_user_admitted(engine: AsyncEngine) -> None:
    """
    Scenario: staff user admitted
      Given Admin(auth=ExternalAuth(get_user=dep, can_access=is_admin))
      When  GET /admin/ is sent with a valid bearer
      Then  the response is 200
      And   the navbar shows the host display name
    """
    _, client = _build(
        engine,
        can_access=lambda user: user.is_staff,
        display_name=lambda user: user.full_name,
    )

    response = client.get("/admin/", headers=_bearer("staff-token"))

    assert response.status_code == 200
    assert "Ada Lovelace" in response.text


def test_has_permission_gates(engine: AsyncEngine) -> None:
    """
    Scenario: has_permission gates
      Given has_permission(user, 'delete_order') returns False
      When  DELETE /admin/order/5 is sent with a valid token
      Then  the response is 403
    """
    _, client = _build(engine, has_permission=lambda user, codename: codename != "delete_bxorder")

    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert response.status_code == 403
    assert anyio.run(_order_exists, engine, 5)


def test_has_permission_grant_is_honoured(engine: AsyncEngine) -> None:
    """
    Scenario: has_permission grants delete
      Given has_permission returns True for every codename
      When  a staff user sends DELETE /admin/bxorder/5
      Then  the response is a 303 to the list
      And   order 5 is deleted
    """
    _, client = _build(engine, has_permission=lambda user, codename: True)

    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert response.status_code == 303
    assert not anyio.run(_order_exists, engine, 5)


def test_object_checker_gets_host_user(engine: AsyncEngine) -> None:
    """
    Scenario: object checker gets host user
      Given an owner_only object checker on Order
      When  GET /admin/order/42 is requested
      Then  the checker was called with the host User instance
    """
    checker = _OwnerOnly()
    _, client = _build(engine, object_checker=checker)

    response = client.get("/admin/bxorder/42", headers=_bearer("staff-token"))

    assert response.status_code == 200
    assert checker.calls
    assert all(isinstance(user, BxHostUser) for user in checker.calls)
    assert checker.calls[0].username == "ada"


def test_object_checker_denial_is_403(engine: AsyncEngine) -> None:
    """
    Scenario: object checker denies another owner's order
      Given an owner_only object checker on Order
      When  the staff user requests GET /admin/bxorder/43 owned by someone else
      Then  the response is 403
    """
    _, client = _build(engine, object_checker=_OwnerOnly())

    response = client.get("/admin/bxorder/43", headers=_bearer("staff-token"))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("other", "value"),
    [("auth_backend", object()), ("otp_service", object())],
)
def test_mutual_exclusion(other: str, value: Any) -> None:
    """
    Scenario: mutual exclusion
      Given both auth= and auth_backend= (or otp_service=)
      When  Admin(...) is constructed
      Then  ValueError names both parameters
    """
    auth = ExternalAuth(get_user=get_current_user)

    with pytest.raises(ValueError, match="auth") as excinfo:
        Admin(FastAPI(), engine=object(), settings=_settings(), auth=auth, **{other: value})

    assert other in str(excinfo.value)


def test_no_hyperadmin_tables_in_bridge_mode(tmp_path: Path) -> None:
    """
    Scenario: no hyperadmin tables in bridge mode
      Given a fresh interpreter importing only hyperadmin and the bridge
      When  the admin mounts and starts
      Then  SQLModel.metadata has no hyperadmin_users table
    """
    code = f"""
        import asyncio

        from fastapi import FastAPI
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlmodel import SQLModel

        from hyperadmin import Admin, HyperAdminSettings
        from hyperadmin.auth import ExternalAuth

        engine = create_async_engine("sqlite+aiosqlite:///{tmp_path / "fresh.db"}")
        admin = Admin(
            FastAPI(),
            engine=engine,
            settings=HyperAdminSettings(secret_key="s", create_tables=True),
            auth=ExternalAuth(get_user=lambda: None),
        )
        admin.mount("/admin")
        asyncio.run(admin.startup())
        print(sorted(t for t in SQLModel.metadata.tables if t.startswith("hyperadmin_")))
    """
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "[]"


# ---------------------------------------------------------------------------
# Review amendments: fail-safe default permissions
# ---------------------------------------------------------------------------


def test_staff_user_is_view_only(engine: AsyncEngine) -> None:
    """
    Scenario: a staff user is view-only
      Given Admin(auth=ExternalAuth(get_user=dep)) without has_permission
      When  the staff user lists orders and then deletes order 5
      Then  the list is 200
      And   the delete is 403 and order 5 still exists
    """
    _, client = _build(engine)

    listing = client.get("/admin/bxorder", headers=_bearer("staff-token"))
    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert listing.status_code == 200
    assert response.status_code == 403
    assert anyio.run(_order_exists, engine, 5)


def test_superuser_has_full_access_by_default(engine: AsyncEngine) -> None:
    """
    Scenario: a superuser has full access by default
      Given Admin(auth=ExternalAuth(get_user=dep)) without has_permission
      When  a superuser sends DELETE /admin/bxorder/5
      Then  the response is a 303 to the list
    """
    _, client = _build(engine)

    response = client.delete("/admin/bxorder/5", headers=_bearer("super-token"))

    assert response.status_code == 303


@pytest.mark.parametrize("allow_full_access", [False, True])
def test_staff_user_cannot_set_own_is_superuser(
    engine: AsyncEngine, allow_full_access: bool
) -> None:
    """
    Scenario: a staff user cannot set their own is_superuser
      Given Admin(auth=ExternalAuth(get_user=dep)) with or without allow_full_access
      When  the staff user PUTs is_superuser=true to their own host user row
      Then  the response is 403
      And   the row is unchanged
    """
    _, client = _build(engine, allow_full_access=allow_full_access)

    response = client.put(
        "/admin/bxhostuser/1",
        data={"username": "ada", "is_staff": "true", "is_superuser": "true"},
        headers=_bearer("staff-token"),
    )

    assert response.status_code == 403
    assert not anyio.run(_is_superuser, engine, 1)


def test_allow_full_access_grants_other_models(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: allow_full_access opts into full access with a warning
      Given ExternalAuth(allow_full_access=True)
      When  the admin is built and a staff user deletes order 5
      Then  a WARNING names allow_full_access
      And   the delete succeeds (303)
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        _, client = _build(engine, allow_full_access=True)

    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert "allow_full_access" in caplog.text
    assert response.status_code == 303


def test_missing_has_permission_logs_warning(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: omitting has_permission logs a startup warning
      Given ExternalAuth without has_permission
      When  the admin is built
      Then  a WARNING names has_permission
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        _build(engine)

    assert "has_permission" in caplog.text


def test_explicit_has_permission_logs_no_warning(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: an explicit has_permission logs no fail-safe warning
      Given ExternalAuth(has_permission=...)
      When  the admin is built
      Then  no WARNING mentions has_permission
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        _build(engine, has_permission=lambda user, codename: True)

    assert "has_permission" not in caplog.text


def test_model_permission_checker_rejected_with_auth() -> None:
    """
    Scenario: ModelPermissionChecker with auth= is rejected
      Given permission_checker=ModelPermissionChecker(...) and auth=ExternalAuth(...)
      When  Admin(...) is constructed without register_auth_models=True
      Then  ValueError names register_auth_models and the int user id requirement
    """
    from hyperadmin.auth.permissions import ModelPermissionChecker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    with pytest.raises(ValueError, match="register_auth_models") as excinfo:
        Admin(
            FastAPI(),
            engine=engine,
            settings=_settings(),
            auth=ExternalAuth(get_user=get_current_user),
            permission_checker=ModelPermissionChecker(engine=engine),
        )

    assert "int" in str(excinfo.value)


def test_model_permission_checker_allowed_with_register_auth_models() -> None:
    """
    Scenario: ModelPermissionChecker with auth= and register_auth_models=True
      Given permission_checker=ModelPermissionChecker(...) and register_auth_models=True
      When  the admin mounts
      Then  the built-in User, Group and Permission admins are registered
      And   the explicit checker (behind the host-user guard) is used
    """
    from hyperadmin.auth.models import Group, Permission, User
    from hyperadmin.auth.permissions import ModelPermissionChecker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    checker = ModelPermissionChecker(engine=engine)
    admin = Admin(
        FastAPI(),
        engine=engine,
        settings=_settings(register_auth_models=True),
        auth=ExternalAuth(get_user=get_current_user),
        permission_checker=checker,
    )
    admin.mount("/admin")

    assert {User, Group, Permission} <= set(site._registry)
    assert isinstance(admin.permission_checker, HostUserModelGuard)
    assert admin.permission_checker.inner is checker


# ---------------------------------------------------------------------------
# Permission checker resolution (first match wins)
# ---------------------------------------------------------------------------


def test_plain_has_permission_is_wrapped(engine: AsyncEngine) -> None:
    """
    Scenario: a plain has_permission callable is wrapped
      Given ExternalAuth(has_permission=<function>)
      When  the admin is built
      Then  the permission checker is a CallablePermissionChecker
    """
    admin, _ = _build(engine, has_permission=lambda user, codename: True)

    assert isinstance(admin.permission_checker, CallablePermissionChecker)


def test_has_permission_checker_object_is_used_as_is(engine: AsyncEngine) -> None:
    """
    Scenario: a PermissionChecker object passed as has_permission is used as is
      Given ExternalAuth(has_permission=<object with has_permission>)
      When  a staff user deletes order 5 and the checker allows only viewing
      Then  the checker is used unwrapped
      And   the delete is 403
    """
    checker = _NamedChecker({"view_bxorder"})
    admin, client = _build(engine, has_permission=checker)

    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert admin.permission_checker is checker
    assert response.status_code == 403


def test_explicit_permission_checker_wins(engine: AsyncEngine) -> None:
    """
    Scenario: an explicit Admin(permission_checker=...) wins over has_permission
      Given Admin(permission_checker=checker) and ExternalAuth(has_permission=...)
      When  a staff user deletes order 5 and then changes their host user row
      Then  the explicit checker decides for orders (303, deleted)
      And   the host user model is still guarded (403)
    """
    app = FastAPI()
    _register()
    checker = _NamedChecker({"delete_bxorder", "change_bxhostuser", "view_bxhostuser"})
    admin = Admin(
        app,
        engine=engine,
        settings=_settings(),
        permission_checker=checker,
        auth=ExternalAuth(get_user=get_current_user, has_permission=lambda u, c: False),
    )
    admin.mount("/admin")
    client = TestClient(app, follow_redirects=False)

    deleted = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))
    changed = client.put(
        "/admin/bxhostuser/1",
        data={"username": "ada", "is_superuser": "true"},
        headers=_bearer("staff-token"),
    )

    assert deleted.status_code == 303
    assert changed.status_code == 403
    assert not anyio.run(_is_superuser, engine, 1)


def test_default_checker_is_guarded_bridge_default(engine: AsyncEngine) -> None:
    """
    Scenario: the fail-safe default checker is the bridge default behind the guard
      Given ExternalAuth without has_permission
      When  the admin is built
      Then  the checker is a HostUserModelGuard around BridgeDefaultPermissionChecker
    """
    admin, _ = _build(engine)

    assert isinstance(admin.permission_checker, HostUserModelGuard)
    assert isinstance(admin.permission_checker.inner, BridgeDefaultPermissionChecker)


# ---------------------------------------------------------------------------
# Routers, middleware, route class and template globals
# ---------------------------------------------------------------------------


def test_anonymous_request_gets_sign_in_page(engine: AsyncEngine) -> None:
    """
    Scenario: an anonymous browser without login_url gets the sign-in page
      Given Admin(auth=ExternalAuth(get_user=dep)) with no login_url
      When  GET /admin/ is sent without credentials
      Then  the response is 401
    """
    _, client = _build(engine)

    response = client.get("/admin/")

    assert response.status_code == 401


def test_anonymous_request_redirects_to_login_url(engine: AsyncEngine) -> None:
    """
    Scenario: an anonymous browser is sent to the host login_url
      Given ExternalAuth(login_url="/login", next_param="return_to")
      When  GET /admin/bxorder is sent without credentials
      Then  the response is a 303 to /login?return_to=/admin/bxorder
    """
    _, client = _build(engine, login_url="/login", next_param="return_to")

    response = client.get("/admin/bxorder")

    assert response.status_code == 303
    assert response.headers["location"] == "/login?return_to=%2Fadmin%2Fbxorder"


def test_can_access_denial_is_403(engine: AsyncEngine) -> None:
    """
    Scenario: a user can_access rejects is denied the whole admin
      Given the default can_access (staff or superuser)
      When  a plain customer sends GET /admin/
      Then  the response is 403
    """
    _, client = _build(engine)

    response = client.get("/admin/", headers=_bearer("customer-token"))

    assert response.status_code == 403


def test_router_mode_protects_admin_routes(engine: AsyncEngine) -> None:
    """
    Scenario: the bridge also protects legacy router mode
      Given Admin(auth=ExternalAuth(...)) with mount_mode="router"
      When  GET /admin/ is sent without, then with, a valid bearer
      Then  the responses are 401 and 200
      And   the host app gets no session or authentication middleware
    """
    from starlette.middleware.sessions import SessionMiddleware

    from hyperadmin.auth.middleware import AuthenticationMiddleware

    with pytest.warns(DeprecationWarning, match="mount_mode"):
        admin, client = _build(engine, mount_mode="router")

    anonymous = client.get("/admin/")
    signed_in = client.get("/admin/", headers=_bearer("staff-token"))

    assert anonymous.status_code == 401
    assert signed_in.status_code == 200
    classes = {m.cls for m in admin.app.user_middleware}
    assert SessionMiddleware not in classes
    assert AuthenticationMiddleware not in classes


def test_bridge_mode_adds_no_session_or_auth_middleware(engine: AsyncEngine) -> None:
    """
    Scenario: bridge mode adds no session or auth middleware and no login routes
      Given Admin(auth=ExternalAuth(...)) in isolated mode
      When  it mounts
      Then  the admin sub-app has no SessionMiddleware or AuthenticationMiddleware
      And   no admin-login or MFA route is registered
    """
    from starlette.middleware.sessions import SessionMiddleware

    from hyperadmin.auth.middleware import AuthenticationMiddleware

    admin, _ = _build(engine)

    assert admin.asgi_app is not None
    classes = {m.cls for m in admin.asgi_app.user_middleware}
    assert SessionMiddleware not in classes
    assert AuthenticationMiddleware not in classes
    names = {getattr(route, "name", None) for route in admin.asgi_app.routes}
    assert "admin-login" not in names
    assert "admin-mfa-challenge" not in names


def test_built_in_auth_models_not_registered_in_bridge_mode(engine: AsyncEngine) -> None:
    """
    Scenario: built-in auth models stay out of bridge mode by default
      Given Admin(auth=ExternalAuth(...)) and register_auth_models unset
      When  it mounts
      Then  no hyperadmin_* model is registered in the admin site
    """
    _build(engine)

    tables = {getattr(model, "__tablename__", "") for model in site._registry}
    assert not {t for t in tables if t.startswith("hyperadmin_")}


def test_template_globals_in_bridge_mode(engine: AsyncEngine) -> None:
    """
    Scenario: bridge mode template globals
      Given ExternalAuth(logout_url="/bye")
      When  the admin mounts
      Then  auth_enabled is True, auth_mode is "external" and logout_url is "/bye"
    """
    admin, _ = _build(engine, logout_url="/bye")

    env_globals = admin.templates.env.globals
    assert env_globals["auth_enabled"] is True
    assert env_globals["auth_mode"] == "external"
    assert env_globals["logout_url"] == "/bye"


def test_csrf_auto_enforces_in_bridge_mode(engine: AsyncEngine) -> None:
    """
    Scenario: csrf_mode="auto" enforces in bridge mode
      Given Admin(auth=ExternalAuth(...)) with the default csrf_mode
      When  a staff user sends DELETE /admin/bxorder/5 without a CSRF token
      Then  the effective CSRF mode is "enforce"
      And   the delete is rejected with 403
    """
    admin, client = _build(
        engine,
        settings=HyperAdminSettings(secret_key=_SECRET),
        has_permission=lambda u, c: True,
    )

    response = client.delete("/admin/bxorder/5", headers=_bearer("staff-token"))

    assert admin.csrf_mode == "enforce"
    assert response.status_code == 403
    assert anyio.run(_order_exists, engine, 5)


def test_token_cookie_is_bridged_into_authorization(engine: AsyncEngine) -> None:
    """
    Scenario: the token cookie authenticates a plain browser navigation
      Given ExternalAuth(token_cookie=TokenCookie()) and CSRF enforced
      When  GET /admin/ is sent with only the hyperadmin_token cookie
      Then  the response is 200
    """
    _, client = _build(
        engine,
        settings=HyperAdminSettings(secret_key=_SECRET),
        token_cookie=TokenCookie(),
    )
    client.cookies.set("hyperadmin_token", "staff-token")

    response = client.get("/admin/")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# HostUserModelGuard
# ---------------------------------------------------------------------------


class TestHostUserModelGuard:
    pytestmark = pytest.mark.anyio

    async def test_denies_change_and_delete_on_host_user_model(self) -> None:
        """
        Scenario: the guard blocks a non-superuser on their own user model
          Given a guard around an allow-everything checker
          When  a staff BxHostUser asks for change_/delete_bxhostuser
          Then  both are denied
          And   other codenames are delegated (allowed)
        """
        guard = HostUserModelGuard(_NamedChecker({"change_bxhostuser", "delete_bxhostuser", "x"}))

        assert not await guard.has_permission(STAFF, "change_bxhostuser")
        assert not await guard.has_permission(STAFF, "delete_bxhostuser")
        assert await guard.has_permission(STAFF, "x")

    async def test_superuser_is_delegated(self) -> None:
        """
        Scenario: a superuser is never blocked by the guard
          Given a guard around a checker allowing change_bxhostuser
          When  a superuser asks for change_bxhostuser
          Then  the inner checker's answer is returned
        """
        guard = HostUserModelGuard(_NamedChecker({"change_bxhostuser"}))

        assert await guard.has_permission(SUPER, "change_bxhostuser")

    async def test_user_permissions_are_delegated(self) -> None:
        """
        Scenario: get_user_permissions is delegated to the inner checker
          Given a guard around a checker enumerating {"view_bxorder"}
          When  get_user_permissions is called
          Then  the inner checker's set is returned
        """
        guard = HostUserModelGuard(_NamedChecker({"view_bxorder"}))

        assert await guard.get_user_permissions(STAFF) == {"view_bxorder"}


def test_bridge_admin_is_noted_for_auth_metadata(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: auth.metadata() warns once a bridge-mode Admin exists
      Given no bridge-mode Admin was built in this process
      When  Admin(auth=ExternalAuth(...)) is built and auth.metadata() is called
      Then  a WARNING names bridge mode
    """
    import hyperadmin.auth as auth_package

    monkeypatch.setattr(auth_package, "_bridge_admin_constructed", False)
    Admin(
        FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=_settings(),
        auth=ExternalAuth(get_user=get_current_user, has_permission=lambda u, c: True),
    )

    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        auth_package.metadata()

    assert "bridge mode" in caplog.text


# ---------------------------------------------------------------------------
# Review follow-ups: bridge-mode logout button and realtime WebSocket auth
# ---------------------------------------------------------------------------


def test_bridge_navbar_has_no_builtin_logout_form(engine: AsyncEngine) -> None:
    """
    Scenario: bridge mode without logout_url renders no dead logout button
      Given Admin(auth=ExternalAuth(get_user=dep)) with no logout_url
      When  an admitted superuser GETs /admin/
      Then  the page has no form posting to the unregistered /admin/logout
      And   no logout button is rendered
    """
    _, client = _build(engine)

    response = client.get("/admin/", headers=_bearer("super-token"))

    assert response.status_code == 200
    assert 'action="/admin/logout"' not in response.text
    assert 'data-testid="logout-btn"' not in response.text


def test_bridge_navbar_logout_posts_to_host_logout_url(engine: AsyncEngine) -> None:
    """
    Scenario: bridge mode with logout_url posts Logout to the host's URL
      Given Admin(auth=ExternalAuth(get_user=dep, logout_url="/auth/logout"))
      When  an admitted superuser GETs /admin/
      Then  the logout form posts to /auth/logout
      And   it does not target the unregistered /admin/logout
    """
    _, client = _build(engine, logout_url="/auth/logout")

    response = client.get("/admin/", headers=_bearer("super-token"))

    assert response.status_code == 200
    assert 'action="/auth/logout"' in response.text
    assert 'action="/admin/logout"' not in response.text


async def _ws_user_from_header(websocket: Any) -> BxHostUser | None:
    """The host's ``websocket_user``: the same bearer lookup on WebSocket scope."""
    return get_current_user(websocket.headers.get("authorization"))


def _build_realtime(engine: AsyncEngine, **auth_kwargs: Any) -> tuple[Admin, TestClient]:
    app = FastAPI()
    _register()
    admin = Admin(
        app,
        engine=engine,
        settings=_settings(),
        realtime=RealtimeSettings(),
        auth=ExternalAuth(get_user=get_current_user, **auth_kwargs),
    )
    admin.mount("/admin")
    return admin, TestClient(app)


def test_bridge_websocket_admits_user_resolved_by_websocket_user(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: realtime WebSocket admits a bridge user passing can_access
      Given Admin(auth=ExternalAuth(websocket_user=hook)) with realtime enabled
      When  a superuser opens /admin/realtime/ws with a valid bearer
      Then  the connection is registered for that user's id
      And   it is not closed as unauthorized
    """
    import hyperadmin.realtime.ws as ws_module

    admin, client = _build_realtime(engine, websocket_user=_ws_user_from_header)
    registry = admin._realtime_registry
    assert registry is not None
    registered: list[set[int]] = []

    async def _one_shot_receive_loop(websocket: Any) -> None:
        # Record the registered users, then end the session server-side.
        registered.append(registry.users())

    monkeypatch.setattr(ws_module, "_receive_loop", _one_shot_receive_loop)

    with (
        client.websocket_connect("/admin/realtime/ws", headers=_bearer("super-token")) as ws,
        pytest.raises(WebSocketDisconnect) as excinfo,
    ):
        ws.receive_bytes()

    assert registered == [{SUPER.id}]
    assert excinfo.value.code != WS_CLOSE_UNAUTHORIZED


@pytest.mark.parametrize(
    ("auth_kwargs", "token"),
    [
        pytest.param({"websocket_user": _ws_user_from_header}, "customer-token", id="can-access"),
        pytest.param({"websocket_user": _ws_user_from_header}, "bogus", id="anonymous"),
        pytest.param({}, "super-token", id="no-websocket-user-hook"),
    ],
)
def test_bridge_websocket_refuses_unadmitted_connections(
    engine: AsyncEngine, auth_kwargs: dict[str, Any], token: str
) -> None:
    """
    Scenario: realtime WebSocket refuses a bridge user who is not admitted
      Given Admin(auth=ExternalAuth(...)) with realtime enabled
      When  a WebSocket opens as a user failing can_access, as an anonymous
            caller, or with no websocket_user hook configured
      Then  the connection is closed with code 4401
    """
    _, client = _build_realtime(engine, **auth_kwargs)

    with (
        client.websocket_connect("/admin/realtime/ws", headers=_bearer(token)) as ws,
        pytest.raises(WebSocketDisconnect) as excinfo,
    ):
        ws.receive_bytes()

    assert excinfo.value.code == WS_CLOSE_UNAUTHORIZED
