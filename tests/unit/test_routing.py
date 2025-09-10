import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.db import create_db_and_tables
from hyperadmin.main import Admin
from hyperadmin.routing import HyperAdminRouter


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    price: float


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def admin_app():
    app = FastAPI()
    admin = Admin(app=app, create_tables=False)
    site.register(Product, ProductAdmin)

    @app.on_event("startup")
    async def startup_event():
        await create_db_and_tables()

    admin.mount(path="/admin")
    return app


from unittest.mock import Mock


def test_hyper_admin_router_instantiation():
    mock_engine = Mock()
    router = HyperAdminRouter(engine=mock_engine)
    assert router.router is not None
    assert router.engine == mock_engine


def test_list_view(admin_app):
    with TestClient(admin_app) as client:
        response = client.get("/admin/product")
        assert response.status_code == 200
        assert "Product" in response.text


def test_detail_view_not_found(admin_app):
    with TestClient(admin_app) as client:
        response = client.get("/admin/product/1")
        assert response.status_code == 404


def test_create_view_get(admin_app):
    with TestClient(admin_app) as client:
        response = client.get("/admin/product/create")
        assert response.status_code == 200
        assert "Create Product" in response.text


def test_update_view_get_not_found(admin_app):
    with TestClient(admin_app) as client:
        response = client.get("/admin/product/1/update")
        assert response.status_code == 404


def test_delete_action_not_found(admin_app):
    with TestClient(admin_app) as client:
        response = client.post("/admin/product/1/delete")
        assert response.status_code == 404


def test_create_item(admin_app):
    with TestClient(admin_app) as client:
        response = client.post(
            "/admin/product/create",
            data={"name": "Test Product", "price": "10.0"},
        )
        assert response.status_code == 200


def test_update_item(admin_app):
    with TestClient(admin_app) as client:
        # First, create an item
        client.post(
            "/admin/product/create",
            data={"name": "Test Product", "price": "10.0"},
        )

        # Then, update it
        response = client.post(
            "/admin/product/1/update",
            data={"name": "Updated Product", "price": "20.0"},
        )
        assert response.status_code == 200


def test_delete_item(admin_app):
    with TestClient(admin_app) as client:
        # First, create an item
        client.post(
            "/admin/product/create",
            data={"name": "Test Product", "price": "10.0"},
        )

        # Then, delete it
        response = client.post("/admin/product/1/delete")
        assert response.status_code == 200
