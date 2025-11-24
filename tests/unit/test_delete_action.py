"""Tests for the delete action."""

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.main import Admin


class ProductTestDelete(SQLModel, table=True):
    __tablename__ = "test_product_delete"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class ProductTestDeleteAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Ensures the site registry is clean before and after each test."""
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client():
    """Provides a TestClient with a clean database for each test."""
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        # Create a sample product
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            product = ProductTestDelete(name="To be deleted")
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, create_tables=False, engine=engine)
    site.register(ProductTestDelete, ProductTestDeleteAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_delete_action_successful(client: TestClient):
    """Test successful deletion."""
    # Ensure item exists
    get_response = client.get("/admin/producttestdelete/1")
    assert get_response.status_code == 200

    # Use DELETE
    response = client.delete("/admin/producttestdelete/1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin/producttestdelete")

    # Verify item is gone
    get_response = client.get("/admin/producttestdelete/1")
    assert get_response.status_code == 404
