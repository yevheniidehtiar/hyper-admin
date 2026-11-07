"""OCC in the update and inline-save views (SDD realtime-occ)."""

from __future__ import annotations

import re
from collections.abc import Iterator

import anyio
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


class OccThing(SQLModel, table=True):
    __tablename__ = "test_occ_thing_views"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    version: int = 1


class OccThingAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    options = AdminOptions(enforce_occ=True, list_editable=["name"])


class LegacyThing(SQLModel, table=True):
    __tablename__ = "test_occ_legacy_views"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    version: int = 1


class LegacyThingAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry() -> Iterator[None]:
    site._registry = {}
    yield
    site._registry = {}


def _client(settings: HyperAdminSettings | None = None) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            session.add(OccThing(name="Bob", version=3))
            session.add(LegacyThing(name="Bob", version=3))
            await session.commit()

    anyio.run(setup)
    admin = Admin(app=app, engine=engine, settings=settings)
    site.register(OccThing, OccThingAdmin)
    site.register(LegacyThing, LegacyThingAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


def _version_of(client: TestClient, kind: str = "occthing") -> str:
    html = client.get(f"/admin/{kind}/1/edit").text
    match = re.search(r'name="__version" value="([^"]*)"', html)
    assert match, "no hidden __version field"
    return match.group(1)


def test_edit_form_renders_hidden_version_field() -> None:
    """
    Scenario: update form renders hidden __version field
      Given OccThing enforces OCC and row 1 has version=3
      When  GET /admin/occthing/1/edit is rendered
      Then  the form contains <input type="hidden" name="__version" value="3">
    """
    assert _version_of(_client()) == "3"


def test_edit_form_has_no_version_field_without_occ() -> None:
    client = _client()
    assert "__version" not in client.get("/admin/legacything/1/edit").text


def test_matching_version_saves_and_bumps() -> None:
    client = _client()
    response = client.put(
        "/admin/occthing/1",
        data={"name": "Alice", "__version": "3"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert _version_of(client) == "4"


def test_stale_version_returns_409_with_conflict_dialog() -> None:
    """
    Scenario: update view returns 409 on stale submit
      Given row 1 has version=3
      When  PUT with __version=2 and new fields
      Then  409, the conflict dialog shows the submitted vs the current values
      And   the row is unchanged
    """
    client = _client()
    response = client.put(
        "/admin/occthing/1",
        data={"name": "Alice", "__version": "2"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 409
    body = response.text
    assert 'data-testid="conflict-dialog"' in body
    assert 'data-testid="conflict-mine-name">Alice<' in body
    assert 'data-testid="conflict-current-name">Bob<' in body
    assert "/admin/occthing/1/edit" in body
    assert 'hx-vals=\'{"__version": "3"}\'' in body
    assert response.headers["HX-Retarget"] == "#ha-occ-conflict"
    assert "Bob" in client.get("/admin/occthing/1/edit").text


def test_override_with_current_version_succeeds() -> None:
    """
    Scenario: conflict dialog "override anyway" re-submits with current version
    """
    client = _client()
    client.put("/admin/occthing/1", data={"name": "X", "__version": "2"})
    response = client.put(
        "/admin/occthing/1",
        data={"name": "Alice", "__version": "3"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert _version_of(client) == "4"


def test_missing_version_is_a_bad_request() -> None:
    """
    Scenario: missing __version field on a configured model returns 400
    """
    client = _client()
    response = client.put("/admin/occthing/1", data={"name": "Alice"})
    assert response.status_code == 400
    assert "Bob" in client.get("/admin/occthing/1/edit").text


def test_legacy_model_ignores_version() -> None:
    """
    Scenario: enforce_occ=False preserves legacy behaviour
      Both a missing and a stale __version are accepted (last write wins).
    """
    client = _client()
    assert client.put("/admin/legacything/1", data={"name": "A"}).status_code in (200, 303)
    assert client.put("/admin/legacything/1", data={"name": "B", "__version": "0"}).status_code in (
        200,
        303,
    )


def test_validation_error_rerender_keeps_original_version() -> None:
    """A 422 re-render carries the version the form was loaded with, not the current one."""
    client = _client()
    response = client.put("/admin/occthing/1", data={"name": "", "__version": "2"})
    assert response.status_code == 422
    assert 'name="__version" value="2"' in response.text


def test_json_409_when_dialog_rendering_is_off() -> None:
    client = _client(HyperAdminSettings(occ_render_dialog=False))
    response = client.put("/admin/occthing/1", data={"name": "Alice", "__version": "2"})
    assert response.status_code == 409
    assert response.json() == {"error": "stale", "current_version": "3"}


def test_inline_editor_carries_version() -> None:
    client = _client()
    html = client.get("/admin/occthing/1/inline/name").text
    assert 'name="__version" value="3"' in html


def test_inline_save_with_matching_version() -> None:
    client = _client()
    response = client.post(
        "/admin/occthing/1/inline/name", data={"name": "Alicia", "__version": "3"}
    )
    assert response.status_code == 200
    assert "Alicia" in response.text
    assert _version_of(client) == "4"


def test_inline_save_stale_returns_409_stale_cell() -> None:
    """
    Scenario: inline cell save returns 409 on stale version
      Then  the cell re-renders the current value with a stale indicator and the row is unchanged
    """
    client = _client()
    response = client.post(
        "/admin/occthing/1/inline/name", data={"name": "Alicia", "__version": "2"}
    )
    assert response.status_code == 409
    assert 'data-testid="cell-stale-name-1"' in response.text
    assert "Bob" in response.text
    assert "Alicia" not in response.text
    assert response.headers["HX-Retarget"] == "#cell-occthing-1-name"
    assert _version_of(client) == "3"


def test_inline_save_stale_json_when_dialog_off() -> None:
    client = _client(HyperAdminSettings(occ_render_dialog=False))
    response = client.post(
        "/admin/occthing/1/inline/name", data={"name": "Alicia", "__version": "2"}
    )
    assert response.status_code == 409
    assert response.json()["error"] == "stale"


def test_inline_save_without_version_is_a_bad_request() -> None:
    client = _client()
    assert client.post("/admin/occthing/1/inline/name", data={"name": "Alicia"}).status_code == 400
