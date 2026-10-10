"""Tests for the update view."""

from datetime import datetime, timezone

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.core.timezones import utc_now


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
            product = ProductTestUpdate(
                name="Old Product", description="Old description", price=10.0, is_active=True
            )
            session.add(product)
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(ProductTestUpdate, ProductTestUpdateAdmin)
    admin.mount(path="/admin")

    return TestClient(app)


def test_update_form_view_renders_form(client: TestClient):
    response = client.get("/admin/producttestupdate/1/edit")
    assert response.status_code == 200
    assert "<form" in response.text
    assert "/admin/producttestupdate/1" in response.text
    assert 'value="Old Product"' in response.text
    assert "Old description" in response.text
    assert 'value="10.0"' in response.text
    assert "checked" in response.text


def test_update_view_successful_submission(client: TestClient):
    form_data = {
        "name": "Updated Product",
        "description": "Updated description",
        "price": "20.0",
        "is_active": "on",
    }
    response = client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    assert response.headers["HX-Redirect"] == "http://testserver/admin/producttestupdate"

    get_response = client.get("/admin/producttestupdate/1")
    assert get_response.status_code == 200
    assert "Updated Product" in get_response.text


def test_update_view_validation_error(client: TestClient):
    form_data = {
        "name": "Updated",
        "description": "Updated description",
        "price": "not-a-number",
    }
    response = client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Input should be a valid number" in response.text
    assert "Updated description" in response.text


def test_update_view_uncheck_boolean(client: TestClient):
    form_data = {
        "name": "Unchecked Product",
        "description": "Desc",
        "price": "10.0",
        # is_active omitted — should become False
    }
    client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    get_response = client.get("/admin/producttestupdate/1")
    assert '"is_active": false' in get_response.text.lower() or "False" in get_response.text


def test_update_view_partial_update_preserves_missing_text_field(client: TestClient):
    form_data = {
        "name": "Partial Update",
        "price": "50.0",
        "is_active": "on",
        # description omitted
    }
    client.put(
        "/admin/producttestupdate/1",
        data=form_data,
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    get_response = client.get("/admin/producttestupdate/1")
    assert "Old description" in get_response.text


# ---------------------------------------------------------------------------
# Auto-now timestamps survive an edit (review of st-v058-byoa-16)
# ---------------------------------------------------------------------------

_SEEDED_AT = datetime(2020, 1, 2, 3, 4, 5)  # noqa: DTZ001 - stored naive in SQLite


class StampedNoteUpdate(SQLModel, table=True):
    __tablename__ = "test_stamped_note_update"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stamped_at: datetime = Field(default_factory=utc_now)


class StampedNoteUpdateAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture
def stamped_client():
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine) as session:
            session.add(StampedNoteUpdate(name="Old", created_at=_SEEDED_AT, stamped_at=_SEEDED_AT))
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(StampedNoteUpdate, StampedNoteUpdateAdmin)
    admin.mount(path="/admin")
    return TestClient(app), engine


def test_editing_a_row_keeps_its_auto_now_timestamps(stamped_client):
    """
    Scenario: auto-now timestamps are not rewritten by an edit
      Given a row whose created_at uses an auto-now default factory
      And   the edit form hides that field
      When  the row is edited via PUT
      Then  the edited field changes and created_at keeps its stored value
    """
    client, engine = stamped_client

    form = client.get("/admin/stampednoteupdate/1/edit")
    assert form.status_code == 200
    assert 'name="created_at"' not in form.text

    response = client.put(
        "/admin/stampednoteupdate/1",
        data={"name": "New"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 200

    async def load() -> StampedNoteUpdate | None:
        async with AsyncSession(engine) as session:
            return await session.get(StampedNoteUpdate, 1)

    row = anyio.run(load)
    assert row is not None
    assert row.name == "New"
    assert row.created_at == _SEEDED_AT
    assert row.stamped_at == _SEEDED_AT
