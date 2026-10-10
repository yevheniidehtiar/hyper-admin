"""Tests for the delete action."""

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings


class ProductTestDelete(SQLModel, table=True):
    __tablename__ = "test_product_delete"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class ProductTestDeleteAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client():
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            product = ProductTestDelete(name="To be deleted")
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(ProductTestDelete, ProductTestDeleteAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_delete_action_successful(client: TestClient):
    get_response = client.get("/admin/producttestdelete/1")
    assert get_response.status_code == 200

    response = client.delete("/admin/producttestdelete/1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin/producttestdelete")

    get_response = client.get("/admin/producttestdelete/1")
    assert get_response.status_code == 404


def test_delete_action_not_found(client: TestClient):
    response = client.delete("/admin/producttestdelete/999", follow_redirects=False)
    assert response.status_code == 404


def test_delete_action_referenced_row_returns_409(client: TestClient, monkeypatch):
    """
    Scenario: deleting a row other records still reference
      Given a product that a foreign key in another table points at
      When  DELETE /admin/producttestdelete/1 is sent
      Then  the response is 409 with an explanation, not a 500
      And   the product still exists
    """
    from sqlalchemy.exc import IntegrityError

    async def referenced(self, pk):
        raise IntegrityError("DELETE", {}, Exception("violates foreign key constraint"))

    monkeypatch.setattr(SQLModelAdapter, "delete", referenced)

    response = client.delete("/admin/producttestdelete/1", follow_redirects=False)

    assert response.status_code == 409
    assert "other records still reference it" in response.text
    monkeypatch.undo()
    assert client.get("/admin/producttestdelete/1").status_code == 200
