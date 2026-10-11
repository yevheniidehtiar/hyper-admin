"""Integration tests for ``build_admin_dependency`` (st-v058-byoa-25, SDD B.1, B.3).

These exercise the dependency as FastAPI actually resolves it — through
``Depends``, on a real route — because the overrides and sub-dependency
scenarios only hold under FastAPI's own dependency-injection machinery.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from hyperadmin.auth.bridge import ExternalAuth, build_admin_dependency
from hyperadmin.core.auth import AdminAccessDenied, AdminAuthenticationRequired


class _HostUser:
    def __init__(self, **attrs: object) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)


def _build_app(auth: ExternalAuth) -> FastAPI:
    app = FastAPI()
    admin_dependency = build_admin_dependency(auth)

    @app.get("/admin")
    async def admin_home(
        request: Request,
        user: Any = Depends(admin_dependency),  # noqa: B008 - FastAPI's own DI idiom
    ):
        return {
            "user_key": request.state.user_key,
            "user_display": request.state.user_display,
            "user_is": user is request.state.user,
        }

    return app


def test_anonymous_raises_authentication_required() -> None:
    """
    Scenario: anonymous raises
      Given the host dependency returns None
      When  the admin dependency resolves
      Then  AdminAuthenticationRequired is raised
    """

    def get_user() -> None:
        return None

    client = TestClient(_build_app(ExternalAuth(get_user=get_user)))

    with pytest.raises(AdminAuthenticationRequired):
        client.get("/admin")


def test_can_access_false_raises_access_denied() -> None:
    """
    Scenario: can_access False raises
      Given can_access returns False
      When  the admin dependency resolves
      Then  AdminAccessDenied is raised
    """

    def get_user() -> _HostUser:
        return _HostUser(is_staff=True)

    auth = ExternalAuth(get_user=get_user, can_access=lambda user: False)
    client = TestClient(_build_app(auth))

    with pytest.raises(AdminAccessDenied):
        client.get("/admin")


def test_state_is_populated_with_the_users_uuid_key() -> None:
    """
    Scenario: state is populated
      Given a host user with a UUID id
      When  the admin dependency resolves
      Then  request.state.user_key is that UUID
    """
    user_id = uuid.uuid4()

    def get_user() -> _HostUser:
        return _HostUser(id=user_id, is_superuser=True, username="alice")

    client = TestClient(_build_app(ExternalAuth(get_user=get_user)))

    response = client.get("/admin")

    assert response.status_code == 200
    body = response.json()
    assert body["user_key"] == str(user_id)
    assert body["user_display"] == "alice"
    assert body["user_is"] is True


def test_dependency_overrides_are_honoured() -> None:
    """
    Scenario: dependency overrides are honoured
      Given app.dependency_overrides replaces the host dependency
      When  an admin route is requested
      Then  the override's user is used
    """

    def get_user() -> None:
        # Would raise AdminAuthenticationRequired if the override below did
        # not take effect.
        return None

    app = _build_app(ExternalAuth(get_user=get_user))
    app.dependency_overrides[get_user] = lambda: _HostUser(
        id=1, is_superuser=True, username="override-user"
    )
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert response.json()["user_display"] == "override-user"


def test_host_dependency_reading_request_app_state_works() -> None:
    """Host dependencies that read ``request.app.state`` resolve normally (SDD B.1)."""

    def get_user(request: Request) -> _HostUser:
        return request.app.state.configured_user

    app = _build_app(ExternalAuth(get_user=get_user))
    app.state.configured_user = _HostUser(id=7, is_superuser=True, username="state-user")
    client = TestClient(app)

    response = client.get("/admin")

    assert response.status_code == 200
    assert response.json()["user_display"] == "state-user"


def test_async_can_access_is_awaited() -> None:
    """A host ``can_access`` may be an ``async def`` (sync/async normalisation)."""

    async def can_access(user: _HostUser) -> bool:
        return bool(user.is_superuser)

    def get_user() -> _HostUser:
        return _HostUser(is_superuser=False, username="bob")

    client = TestClient(_build_app(ExternalAuth(get_user=get_user, can_access=can_access)))

    with pytest.raises(AdminAccessDenied):
        client.get("/admin")
