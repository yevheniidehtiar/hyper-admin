"""Permission-aware sidebar and HTML error pages for admin routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class ErrPageVisible(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class ErrPageHidden(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


@dataclass
class _User:
    id: int = 1
    username: str = "viewer"
    is_superuser: bool = False


class _Backend:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> _User:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _Checker:
    """Grants view and delete on ErrPageVisible only (superusers get everything)."""

    granted = frozenset({"view_errpagevisible", "delete_errpagevisible"})

    async def has_permission(self, user: Any, codename: str) -> bool:
        return user.is_superuser or codename in self.granted

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted)


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _client(user: _User) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                SQLModel.metadata.create_all,
                tables=[ErrPageVisible.__table__, ErrPageHidden.__table__],
            )

    anyio.run(_setup)
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="x" * 40),
        auth_backend=_Backend(user),
        permission_checker=_Checker(),
    )
    site.register(ErrPageVisible)
    site.register(ErrPageHidden)
    admin.mount(path="/admin")
    return TestClient(app)


HTML = {"accept": "text/html"}


def test_sidebar_hides_models_the_user_cannot_view() -> None:
    """
    Scenario: a restricted user sees only the models they may view
      Given a user with view permission on ErrPageVisible only
      When  they open the admin dashboard
      Then  the sidebar links to ErrPageVisible and not to ErrPageHidden
    """
    page = _client(_User()).get("/admin/", headers=HTML)

    assert page.status_code == 200
    assert 'href="/admin/errpagevisible"' in page.text
    assert 'href="/admin/errpagehidden"' not in page.text


def test_superuser_sidebar_lists_every_model() -> None:
    page = _client(_User(is_superuser=True)).get("/admin/", headers=HTML)

    assert 'href="/admin/errpagevisible"' in page.text
    assert 'href="/admin/errpagehidden"' in page.text


def test_forbidden_page_renders_inside_the_admin_layout() -> None:
    """
    Scenario: a browser opens a model the user may not view
      Given a user without view permission on ErrPageHidden
      When  the browser requests /admin/errpagehidden
      Then  the response is 403 with an HTML error page in the admin layout
    """
    page = _client(_User()).get("/admin/errpagehidden", headers=HTML)

    assert page.status_code == 403
    assert page.headers["content-type"].startswith("text/html")
    assert 'data-testid="error-page"' in page.text
    assert 'data-testid="sidebar"' in page.text


def test_forbidden_htmx_request_returns_a_toast_on_the_current_page() -> None:
    """
    Scenario: an HTMX action is refused
      Given a user without delete permission on ErrPageHidden
      When  an HTMX DELETE is sent
      Then  the response is a 403 toast retargeted to the toast region
    """
    response = _client(_User()).delete("/admin/errpagehidden/1", headers={"HX-Request": "true"})

    assert response.status_code == 403
    assert 'data-testid="error-toast"' in response.text
    assert response.headers["HX-Retarget"] == ".ha-toast-container"
    assert response.headers["HX-Reswap"] == "beforeend"


def test_api_clients_still_get_json_errors() -> None:
    response = _client(_User()).get("/admin/errpagehidden", headers={"accept": "application/json"})

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}
