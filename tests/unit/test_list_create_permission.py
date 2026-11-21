"""The list page's "Create <model>" button follows the add permission.

The create routes answer 403 without ``add_<model>``; the list page must not
offer a button that leads there.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class CreateGateItem(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = "x"


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _Backend:
    """Signs every request in as a non-superuser."""

    async def get_current_user(self, request: Any) -> Any:
        return SimpleNamespace(id=1, username="bob", is_superuser=False, is_active=True)

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _GrantedChecker:
    """Permission checker granting a fixed set of codenames."""

    def __init__(self, *granted: str) -> None:
        self.granted = set(granted)

    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in self.granted

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(self.granted)


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _client(*granted: str, **options: Any) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=True, secret_key="test-secret"),
        auth_backend=_Backend(),
        permission_checker=_GrantedChecker(*granted),
    )
    site.register(CreateGateItem, _Admin, options=AdminOptions(**options))
    admin.mount(path="/admin")
    return TestClient(app)


def test_a_read_only_user_gets_no_create_button() -> None:
    """
    Scenario: a user without add permission sees no Create button
      Given bob holds view_creategateitem but not add_creategateitem
      When  bob opens the list page
      Then  the page has no "Create" link
      And   the create form still answers 403
    """
    with _client("view_creategateitem") as client:
        page = client.get("/admin/creategateitem")
        form = client.get("/admin/creategateitem/create")

    assert page.status_code == 200
    assert 'data-testid="create-link"' not in page.text
    assert form.status_code == 403


def test_a_user_with_add_permission_gets_the_create_button() -> None:
    """
    Scenario: a user with add permission sees the Create button
      Given alice holds view_creategateitem and add_creategateitem
      When  alice opens the list page
      Then  the page links to the create form
    """
    with _client("view_creategateitem", "add_creategateitem") as client:
        page = client.get("/admin/creategateitem")

    assert 'data-testid="create-link"' in page.text
    assert '/admin/creategateitem/create"' in page.text


def test_a_disabled_create_page_hides_the_button_whatever_the_permissions() -> None:
    """
    Scenario: can_create=False wins over the add permission
      Given AdminOptions(can_create=False)
      And   alice holds add_creategateitem
      When  alice opens the list page
      Then  the page has no "Create" link
    """
    with _client("view_creategateitem", "add_creategateitem", can_create=False) as client:
        page = client.get("/admin/creategateitem")

    assert 'data-testid="create-link"' not in page.text
