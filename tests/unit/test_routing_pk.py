"""Unit tests for per-model primary-key routing (st-v058-byoa-28, BYOA SDD A.5).

Covers the ``hyperadmin_pk`` URL convertor, the per-model item-segment
convertor choice, literal-route-before-item-route registration order, and
composite-key list-only registration.
"""

from __future__ import annotations

import logging
import uuid
from unittest.mock import MagicMock
from urllib.parse import quote, unquote

import anyio
import pytest
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import HyperAdminPkConvertor, create_admin_router

# ---------------------------------------------------------------------------
# Fixture models
# ---------------------------------------------------------------------------


class IntPkWidget(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = "widget"


class UuidPkWidget(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = "widget"


class StrPkWidget(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    code: str = Field(primary_key=True)
    name: str = "widget"


class CompositePkWidget(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    a: int = Field(primary_key=True)
    b: int = Field(primary_key=True)
    name: str = "widget"


class _WidgetAdmin(ModelAdmin):
    """Generic ``ModelAdmin`` reused across models; ``site.register`` fills in
    ``adapter_class`` via its own adapter-detection, so nothing is set here."""


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Ensures the site registry is clean before and after each test."""
    site._registry = {}
    yield
    site._registry = {}


def _mount(model: type[SQLModel], *, options: AdminOptions | None = None):
    """Mounts ``model`` under ``/admin`` on a fresh app; returns (client, app, engine)."""
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(model, _WidgetAdmin, options=options or AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app), app, engine


def _build_router(model: type[SQLModel], *, options: AdminOptions | None = None):
    """Builds a bare router via ``create_admin_router``, with mocked templates."""
    site.register(model, _WidgetAdmin, options=options or AdminOptions())
    admin_class = site._registry[model]
    admin_instance = admin_class(model)
    engine = create_async_engine("sqlite+aiosqlite://")
    return create_admin_router(
        model=model,
        admin_class=admin_class,
        admin_instance=admin_instance,
        options=admin_class.options,
        engine=engine,
        templates=MagicMock(spec=Jinja2Templates),
    )


# ---------------------------------------------------------------------------
# Scenario: int paths unchanged
# ---------------------------------------------------------------------------


def test_int_pk_paths_unchanged():
    """
    Scenario: int paths unchanged
      Given an int-id model
      When  routes are generated
      Then  paths contain '{item_id:int}'
    """
    router = _build_router(IntPkWidget)

    by_name = {route.name: route for route in router.routes}
    assert by_name["intpkwidget-detail"].path == "/intpkwidget/{item_id:int}"
    assert by_name["intpkwidget-update"].path == "/intpkwidget/{item_id:int}"
    assert by_name["intpkwidget-delete"].path == "/intpkwidget/{item_id:int}"
    assert by_name["intpkwidget-update-form"].path == "/intpkwidget/{item_id:int}/edit"


def test_uuid_pk_uses_starlette_uuid_convertor():
    """A UUID-pk model's item routes use Starlette's built-in `uuid` convertor."""
    router = _build_router(UuidPkWidget)

    by_name = {route.name: route for route in router.routes}
    assert by_name["uuidpkwidget-detail"].path == "/uuidpkwidget/{item_id:uuid}"


def test_str_pk_uses_hyperadmin_pk_convertor():
    """A natural str-pk model's item routes use the custom `hyperadmin_pk` convertor."""
    router = _build_router(StrPkWidget)

    by_name = {route.name: route for route in router.routes}
    assert by_name["strpkwidget-detail"].path == "/strpkwidget/{item_id:hyperadmin_pk}"


# ---------------------------------------------------------------------------
# Scenario: malformed UUID 404
# ---------------------------------------------------------------------------


def test_malformed_uuid_returns_404():
    """
    Scenario: malformed UUID 404
      Given a UUID model
      When  GET /m/not-a-uuid is requested
      Then  the status is 404
    """
    client, _app, _engine = _mount(UuidPkWidget)

    response = client.get("/admin/uuidpkwidget/not-a-uuid")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Scenario: literal route wins
# ---------------------------------------------------------------------------


def test_literal_route_wins_over_item_id_for_str_pk():
    """
    Scenario: literal route wins
      Given a str-pk model
      When  GET /m/create-popup?target=x is requested
      Then  the popup view handles it
    """
    client, _app, _engine = _mount(StrPkWidget)

    response = client.get("/admin/strpkwidget/create-popup", params={"target": "name"})

    # Mis-routed to detail_view(item_id: int) with item_id="create-popup" would
    # 422 (FastAPI can't coerce the literal to int). Routed correctly, the
    # popup-create view renders its form fragment.
    assert response.status_code == 200
    assert 'data-testid="popup-form"' in response.text


# ---------------------------------------------------------------------------
# Scenario: special characters round-trip
# ---------------------------------------------------------------------------


def test_hyperadmin_pk_convertor_round_trips_special_characters():
    """
    Scenario: special characters round-trip
      Given a str pk 'a b?c'
      When  url_for(detail) runs
      Then  the path is percent-encoded and resolves back to 'a b?c'
    """
    convertor = HyperAdminPkConvertor()
    raw = "a b?c"

    encoded = convertor.to_string(raw)

    assert encoded == quote(raw, safe="-._~!$&'()*+,;=:@")
    assert " " not in encoded
    assert "?" not in encoded
    # Real ASGI servers decode the path segment before Starlette ever calls
    # `convert()` (scope["path"] is already percent-decoded), so this is
    # exactly what happens on a real request for this URL.
    assert convertor.convert(unquote(encoded)) == raw


def test_hyperadmin_pk_convertor_rejects_empty_and_slash_values():
    convertor = HyperAdminPkConvertor()

    with pytest.raises(ValueError, match="Invalid primary key"):
        convertor.to_string("")

    with pytest.raises(ValueError, match="Invalid primary key"):
        convertor.to_string("a/b")


def test_str_pk_detail_url_is_percent_encoded_for_special_characters():
    """The generated detail route for a str-pk model percent-encodes url_for() output."""
    _client, app, _engine = _mount(StrPkWidget)

    url = app.url_path_for("strpkwidget-detail", item_id="a b?c")

    assert "%20" in str(url)
    assert "%3F" in str(url)
    assert " " not in str(url)
    assert "?" not in str(url)


# ---------------------------------------------------------------------------
# Scenario: composite list-only
# ---------------------------------------------------------------------------


def test_composite_pk_registers_list_and_choices_routes_only(caplog):
    """
    Scenario: composite list-only
      Given a composite-pk model
      When  routes are generated
      Then  only list and choices routes exist
      And   a warning is logged
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin.routing"):
        router = _build_router(CompositePkWidget, options=AdminOptions(list_display=["a", "b"]))

    names = {route.name for route in router.routes}
    assert names == {"compositepkwidget-list", "compositepkwidget-choices"}
    assert any(
        "composite primary key" in record.message and "registering list-only" in record.message
        for record in caplog.records
    )


def test_composite_pk_forces_options_off():
    """The review amendment: composite registration forces off detail/edit/delete/create,
    list_editable and inlines, and strips actions, so templates never call url_for on a
    route that was never registered."""
    site.register(
        CompositePkWidget,
        _WidgetAdmin,
        options=AdminOptions(
            list_display=["a", "b"],
            list_editable=["name"],
        ),
    )
    admin_class = site._registry[CompositePkWidget]
    admin_instance = admin_class(CompositePkWidget)
    engine = create_async_engine("sqlite+aiosqlite://")

    router = create_admin_router(
        model=CompositePkWidget,
        admin_class=admin_class,
        admin_instance=admin_instance,
        options=admin_class.options,
        engine=engine,
        templates=MagicMock(spec=Jinja2Templates),
        actions=[MagicMock(bulk=True, name="dummy")],
    )

    names = {route.name for route in router.routes}
    assert names == {"compositepkwidget-list", "compositepkwidget-choices"}


def test_composite_pk_list_page_returns_200_with_no_row_links():
    """
    Scenario: composite list page with no row links
      Given a composite-pk model with one row
      When  GET /m (list) is requested
      Then  the response is 200 with no view/edit/delete row links
    """
    client, _app, engine = _mount(CompositePkWidget, options=AdminOptions(list_display=["a", "b"]))

    async def seed():
        async with engine.begin() as conn:
            await conn.execute(CompositePkWidget.__table__.insert().values(a=1, b=2, name="x"))

    anyio.run(seed)

    response = client.get("/admin/compositepkwidget")

    assert response.status_code == 200
    assert 'data-testid="list-table"' in response.text
    assert 'data-testid="row-view-link"' not in response.text
    assert 'data-testid="row-edit-link"' not in response.text
    assert 'data-testid="row-delete-btn"' not in response.text
