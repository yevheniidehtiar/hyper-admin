"""Bridge-aware navbar and the CSRF reload banner (st-v058-byoa-46, SDD D.1).

A real admin is mounted in bridge mode (``Admin(auth=ExternalAuth(...))``) with
CSRF enforced, and its rendered pages are inspected.
"""

from __future__ import annotations

import re
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

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class NbHostUser(SQLModel, table=True):
    """The host application's own user model."""

    __tablename__ = "nb_host_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    full_name: str = ""
    is_staff: bool = False
    is_superuser: bool = False


class NbOrder(SQLModel, table=True):
    __tablename__ = "nb_order"

    id: int | None = Field(default=None, primary_key=True)
    status: str = "new"


class NbOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


ADA = NbHostUser(id=1, username="ada", full_name="Ada", is_staff=True, is_superuser=True)


def get_current_user(authorization: str | None = Header(default=None)) -> NbHostUser | None:
    """The host's ``get_user``: one valid bearer token."""
    return ADA if authorization == "Bearer ada-token" else None


_BEARER = {"Authorization": "Bearer ada-token"}


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
def engine(tmp_path: Path) -> AsyncEngine:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'navbar.db'}")

    async def _seed() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                SQLModel.metadata.create_all,
                tables=[NbHostUser.__table__, NbOrder.__table__],  # type: ignore[attr-defined]
            )
        async with AsyncSession(engine) as session:
            session.add(NbOrder(id=5))
            await session.commit()

    anyio.run(_seed)
    return engine


def _client(engine: AsyncEngine, *, csrf_mode: str = "enforce", **auth_kwargs: Any) -> TestClient:
    app = FastAPI()
    site.register(NbOrder, NbOrderAdmin)
    Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(secret_key="navbar-test-secret", csrf_mode=csrf_mode),
        auth=ExternalAuth(get_user=get_current_user, **auth_kwargs),
    ).mount("/admin")
    return TestClient(app, follow_redirects=False)


def test_bridged_navbar_shows_the_host_display_name(engine: AsyncEngine) -> None:
    """
    Scenario: bridged navbar
      Given a bridged user with display name 'Ada'
      When  the dashboard renders
      Then  the navbar shows 'Ada'
    """
    client = _client(engine, display_name=lambda user: user.full_name)

    response = client.get("/admin/", headers=_BEARER)

    assert response.status_code == 200
    assert re.search(r'data-testid="current-user">\s*Ada\s*<', response.text)


def test_bridged_navbar_logout_goes_through_the_admin_then_the_host_logout_url(
    engine: AsyncEngine,
) -> None:
    """
    Scenario: bridged navbar logout clears the admin cookie, then reaches the host
      Given a bridged admin with logout_url '/auth/logout' and CSRF enforced
      When  the dashboard renders and the navbar logout form is submitted
      Then  the form posts to the admin's own /admin/logout with the admin CSRF token
      And   that route redirects to the host's /auth/logout
    """
    client = _client(engine, logout_url="/auth/logout")

    response = client.get("/admin/", headers=_BEARER)

    form = re.search(
        r'<form method="post" action="/admin/logout">(.*?)</form>', response.text, re.DOTALL
    )
    assert form is not None
    assert 'data-testid="logout-btn"' in form.group(1)
    token = re.search(r'name="csrf_token" value="([^"]+)"', form.group(1))
    assert token is not None

    logout = client.post("/admin/logout", headers=_BEARER, data={"csrf_token": token.group(1)})
    assert logout.status_code == 303
    assert logout.headers["location"] == "/auth/logout"


def test_admin_page_ships_a_hidden_csrf_reload_banner(engine: AsyncEngine) -> None:
    """
    Scenario: admin page ships a hidden CSRF reload banner
      Given a bridged admin with CSRF enforced
      When  the dashboard renders
      Then  the page holds a csrf-reload-banner that starts hidden
      And   it offers a reload-page button
      And   the page's HTMX hook reveals it on a 403 carrying X-HyperAdmin-CSRF
    """
    client = _client(engine)

    response = client.get("/admin/", headers=_BEARER)

    banner = re.search(
        r'<div([^>]*)data-testid="csrf-reload-banner"[^>]*>(.*?)aria-label="Close"',
        response.text,
        re.DOTALL,
    )
    assert banner is not None
    assert "x-cloak" in banner.group(1)
    assert 'x-show="show"' in banner.group(1)
    assert "location.reload()" in banner.group(2)
    assert "Reload page" in banner.group(2)
    assert "getResponseHeader('X-HyperAdmin-CSRF')" in response.text
    assert "ha-csrf-failed" in response.text


def test_no_csrf_reload_banner_when_csrf_is_off(engine: AsyncEngine) -> None:
    """
    Scenario: no CSRF reload banner when CSRF is off
      Given a bridged admin with csrf_mode 'off'
      When  the dashboard renders
      Then  the page holds no csrf-reload-banner
    """
    client = _client(engine, csrf_mode="off")

    response = client.get("/admin/", headers=_BEARER)

    assert response.status_code == 200
    assert 'data-testid="csrf-reload-banner"' not in response.text


def test_csrf_reload_banner_stays_out_of_the_error_toast_region(engine: AsyncEngine) -> None:
    """
    Scenario: CSRF reload banner stays out of the error-toast region
      Given a bridged admin with CSRF enforced
      When  the dashboard renders
      Then  the page holds exactly one .ha-toast-container (the messages region)
      And   the csrf-reload-banner sits in its own ha-csrf-banner-region wrapper
    """
    client = _client(engine)

    response = client.get("/admin/", headers=_BEARER)

    assert response.status_code == 200
    assert len(re.findall(r'class="ha-toast-container"', response.text)) == 1
    region = re.search(
        r'<div class="ha-csrf-banner-region">\s*<div[^>]*data-testid="csrf-reload-banner"',
        response.text,
    )
    assert region is not None
