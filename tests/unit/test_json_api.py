"""Unit tests for JsonApiRouter CRUD endpoint generation."""

from __future__ import annotations

from unittest.mock import MagicMock

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.views.json_api import (
    _DEFAULT_PAGE_SIZE,
    _MAX_PAGE_SIZE,
    DeletedEnvelope,
    DetailEnvelope,
    JsonApiRouter,
    ListEnvelope,
    PaginationMeta,
)


class Item(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float = 0.0


class ItemAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure each test starts with a fresh registry."""
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.from_thread.run(
        lambda: _init_db(eng),
    )
    return eng


async def _init_db(eng):
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@pytest.fixture
def app_with_api():
    """Create a FastAPI app with JsonApiRouter mounted."""

    def _factory(options: AdminOptions | None = None):
        app = FastAPI()
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")

        async def setup():
            async with eng.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

        anyio.run(setup)

        site.register(Item, ItemAdmin, options=options or AdminOptions())
        json_router = JsonApiRouter(engine=eng)
        json_router.generate_routes()
        app.include_router(json_router.get_router(), prefix="/api")
        return TestClient(app), eng

    return _factory


# ---------------------------------------------------------------------------
# Route generation tests
# ---------------------------------------------------------------------------


class TestRouteGeneration:
    """Verify the correct routes are generated based on AdminOptions."""

    def test_all_crud_routes_generated_by_default(self, app_with_api):
        client, _ = app_with_api()
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-list" in routes
        assert "api-item-detail" in routes
        assert "api-item-create" in routes
        assert "api-item-update" in routes
        assert "api-item-delete" in routes

    def test_list_disabled(self, app_with_api):
        client, _ = app_with_api(AdminOptions(can_list=False))
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-list" not in routes
        assert "api-item-detail" in routes

    def test_create_disabled(self, app_with_api):
        client, _ = app_with_api(AdminOptions(can_create=False))
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-create" not in routes

    def test_edit_disabled(self, app_with_api):
        client, _ = app_with_api(AdminOptions(can_edit=False))
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-update" not in routes

    def test_delete_disabled(self, app_with_api):
        client, _ = app_with_api(AdminOptions(can_delete=False))
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-delete" not in routes

    def test_detail_disabled(self, app_with_api):
        client, _ = app_with_api(AdminOptions(can_detail=False))
        routes = {r.name for r in client.app.routes if hasattr(r, "name")}
        assert "api-item-detail" not in routes


# ---------------------------------------------------------------------------
# Endpoint behavior tests
# ---------------------------------------------------------------------------


class TestListEndpoint:
    """GET /api/item — paginated listing."""

    def test_empty_list(self, app_with_api):
        client, _ = app_with_api()
        resp = client.get("/api/item")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["pagination"]["page"] == 1
        assert body["pagination"]["total"] == 0
        assert body["pagination"]["total_pages"] == 1

    def test_default_page_size(self, app_with_api):
        client, _ = app_with_api()
        resp = client.get("/api/item")
        assert resp.json()["pagination"]["page_size"] == _DEFAULT_PAGE_SIZE

    def test_custom_page_size(self, app_with_api):
        client, _ = app_with_api()
        resp = client.get("/api/item?page_size=10")
        assert resp.status_code == 200
        assert resp.json()["pagination"]["page_size"] == 10

    def test_page_size_exceeds_max(self, app_with_api):
        client, _ = app_with_api()
        resp = client.get(f"/api/item?page_size={_MAX_PAGE_SIZE + 1}")
        assert resp.status_code == 422  # validation error

    def test_list_with_items(self, app_with_api):
        client, _ = app_with_api()
        # Create items first
        client.post("/api/item", json={"name": "Widget", "price": 9.99})
        client.post("/api/item", json={"name": "Gadget", "price": 19.99})
        resp = client.get("/api/item")
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert len(body["data"]) == 2

    def test_pagination(self, app_with_api):
        client, _ = app_with_api()
        for i in range(5):
            client.post("/api/item", json={"name": f"Item {i}", "price": float(i)})
        resp = client.get("/api/item?page=1&page_size=2")
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total"] == 5
        assert body["pagination"]["total_pages"] == 3


class TestDetailEndpoint:
    """GET /api/item/{id} — single item."""

    def test_detail_found(self, app_with_api):
        client, _ = app_with_api()
        client.post("/api/item", json={"name": "Widget", "price": 9.99})
        resp = client.get("/api/item/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Widget"

    def test_detail_not_found(self, app_with_api):
        client, _ = app_with_api()
        resp = client.get("/api/item/999")
        assert resp.status_code == 404


class TestCreateEndpoint:
    """POST /api/item — create a new item."""

    def test_create_success(self, app_with_api):
        client, _ = app_with_api()
        resp = client.post("/api/item", json={"name": "New Item", "price": 5.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["name"] == "New Item"
        assert body["data"]["id"] is not None


class TestUpdateEndpoint:
    """PUT /api/item/{id} — update an existing item."""

    def test_update_success(self, app_with_api):
        client, _ = app_with_api()
        client.post("/api/item", json={"name": "Old Name", "price": 1.0})
        resp = client.put("/api/item/1", json={"name": "New Name", "price": 2.0})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "New Name"


class TestDeleteEndpoint:
    """DELETE /api/item/{id} — delete an item."""

    def test_delete_success(self, app_with_api):
        client, _ = app_with_api()
        client.post("/api/item", json={"name": "Doomed", "price": 0.0})
        resp = client.delete("/api/item/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] is True
        assert body["id"] == 1
        # Verify it's gone
        resp = client.get("/api/item/1")
        assert resp.status_code == 404

    def test_delete_not_found(self, app_with_api):
        client, _ = app_with_api()
        resp = client.delete("/api/item/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response model / schema tests
# ---------------------------------------------------------------------------


class TestResponseModels:
    """Verify Pydantic response models serialize correctly."""

    def test_pagination_meta(self):
        meta = PaginationMeta(page=2, page_size=10, total=25, total_pages=3)
        d = meta.model_dump()
        assert d == {"page": 2, "page_size": 10, "total": 25, "total_pages": 3}

    def test_list_envelope(self):
        env = ListEnvelope(
            data=[{"id": 1, "name": "x"}],
            pagination=PaginationMeta(page=1, page_size=50, total=1, total_pages=1),
        )
        d = env.model_dump()
        assert len(d["data"]) == 1
        assert d["pagination"]["total"] == 1

    def test_detail_envelope(self):
        env = DetailEnvelope(data={"id": 1, "name": "x"})
        assert env.model_dump()["data"]["name"] == "x"

    def test_deleted_envelope(self):
        env = DeletedEnvelope(deleted=True, id=1)
        assert env.model_dump() == {"deleted": True, "id": 1}


# ---------------------------------------------------------------------------
# HyperAdminRouter integration
# ---------------------------------------------------------------------------


class TestHyperAdminRouterIntegration:
    """Verify that HyperAdminRouter includes JSON API routes."""

    def test_json_api_routes_in_hyper_admin_router(self):

        from fastapi.templating import Jinja2Templates

        from hyperadmin.routing import HyperAdminRouter

        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        templates = MagicMock(spec=Jinja2Templates)
        templates.env = MagicMock()
        templates.env.trim_blocks = True
        templates.env.lstrip_blocks = True
        templates.env.globals = {}

        site.register(Item, ItemAdmin)

        router_gen = HyperAdminRouter(engine=eng, templates=templates)
        router_gen.generate_routes()
        routers = router_gen.get_routers()

        # Find the API router (the one with /api prefix)
        all_route_names: set[str] = set()
        for r in routers:
            for route in r.routes:
                if hasattr(route, "name") and route.name:
                    all_route_names.add(route.name)

        assert "api-item-list" in all_route_names
        assert "api-item-detail" in all_route_names
        assert "api-item-create" in all_route_names
        assert "api-item-update" in all_route_names
        assert "api-item-delete" in all_route_names
