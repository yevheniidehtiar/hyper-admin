"""Tests for the update view."""

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


class ProductTestUpdate(SQLModel, table=True):
    __tablename__ = "test_product_update"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price: float
    is_active: bool = Field(default=True)


class ProductTestUpdateAdmin(ModelAdmin):
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
            product = ProductTestUpdate(
                name="Old Product", description="Old description", price=10.0, is_active=True
            )
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, create_tables=False, engine=engine)
    site.register(ProductTestUpdate, ProductTestUpdateAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_update_form_view_renders_form(client: TestClient):
    """Test that the update form view renders a form with the correct fields and values."""
    response = client.get("/admin/producttestupdate/1/edit")
    assert response.status_code == 200
    assert "<form" in response.text
    assert "/admin/producttestupdate/1" in response.text
    assert 'value="Old Product"' in response.text
    assert "Old description" in response.text
    assert 'value="10.0"' in response.text
    # Checkbox should be checked
    assert "checked" in response.text


def test_update_view_successful_submission(client: TestClient):
    """Test successful form submission updates the record and redirects."""
    form_data = {
        "name": "Updated Product",
        "description": "Updated description",
        "price": "20.0",
        "is_active": "on",  # Checkbox checked
    }
    headers = {"HX-Request": "true"}
    # Use PUT
    response = client.put(
        "/admin/producttestupdate/1", data=form_data, headers=headers, follow_redirects=False
    )

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert response.headers["HX-Redirect"] == "http://testserver/admin/producttestupdate"

    # Verify the item was updated in the database
    get_response = client.get("/admin/producttestupdate/1")
    assert get_response.status_code == 200
    assert "Updated Product" in get_response.text


def test_update_view_validation_error(client: TestClient):
    """Test that submitting invalid data returns the form with errors."""
    form_data = {
        "name": "Updated",
        "description": "Updated description",
        "price": "not-a-number",  # invalid float
    }
    headers = {"HX-Request": "true"}
    # Use PUT
    response = client.put(
        "/admin/producttestupdate/1", data=form_data, headers=headers, follow_redirects=False
    )

    # We expect a 422 and validation errors
    assert response.status_code == 422
    assert "Input should be a valid number" in response.text
    assert "Updated description" in response.text


def test_update_view_uncheck_boolean(client: TestClient):
    """Test that omitting a boolean field unchecks it."""
    form_data = {
        "name": "Unchecked Product",
        "description": "Desc",
        "price": "10.0",
        # is_active missing -> should be False
    }
    headers = {"HX-Request": "true"}
    client.put(
        "/admin/producttestupdate/1", data=form_data, headers=headers, follow_redirects=False
    )

    # Verify DB
    # We can't easily verify DB directly without async setup, but we can verify via GET detail
    # Assume detail view shows value
    get_response = client.get("/admin/producttestupdate/1")
    # SQLModelAdapter list/get returns dict or model. Detail view renders dict.
    # We need to parse response or trust adapter update worked.
    # The previous value was True. Default is True.
    # If update worked, it should be False.
    # But wait, detail template might not show False explicitly if not customised?
    # It loops over items.
    assert '"is_active": false' in get_response.text.lower() or "False" in get_response.text


def test_update_view_partial_update_skips_missing_text_field(client: TestClient):
    """Test that omitting a text field (that is NOT a checkbox) preserves existing value."""
    form_data = {
        "name": "Partial Update",
        "price": "50.0",
        "is_active": "on",
        # description missing
    }
    headers = {"HX-Request": "true"}
    client.put(
        "/admin/producttestupdate/1", data=form_data, headers=headers, follow_redirects=False
    )

    get_response = client.get("/admin/producttestupdate/1")
    # Description should be "Old description" (preserved), NOT default/empty.
    assert "Old description" in get_response.text
