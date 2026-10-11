"""Unit tests for ``hyperadmin.core.discovery.build_filter_metadata``."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.discovery import build_filter_metadata

# ---------------------------------------------------------------------------
# Story scenario (st-v058-byoa-23)
# ---------------------------------------------------------------------------


class DiscoveryCategory(SQLModel, table=True):
    __tablename__ = "discovery_category"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str


class DiscoveryProduct(SQLModel, table=True):
    __tablename__ = "discovery_product"

    id: int | None = Field(default=None, primary_key=True)
    category_id: uuid.UUID = Field(foreign_key="discovery_category.id")
    category: DiscoveryCategory | None = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest.mark.anyio
async def test_fk_filter_choice_values_are_uuid_strings(engine) -> None:
    """
    Scenario: FK filter choices
      Given an FK to a UUID model
      When  filter metadata is built
      Then  choice values are UUID strings
    """
    category_id = uuid.uuid4()
    category_adapter = SQLModelAdapter(DiscoveryCategory, engine)
    await category_adapter.create({"id": category_id, "name": "Widgets"})

    product_adapter = SQLModelAdapter(DiscoveryProduct, engine)

    metadata = await build_filter_metadata(DiscoveryProduct, ["category_id"], product_adapter)

    assert len(metadata) == 1
    fk_filter = metadata[0]
    assert fk_filter["type"] == "fk"
    assert fk_filter["choices"] == [
        {"value": str(category_id), "label": "Widgets"},
    ]
    # The value is the canonical (lowercase, hyphenated) UUID string, not repr(UUID).
    assert isinstance(fk_filter["choices"][0]["value"], str)
    uuid.UUID(fk_filter["choices"][0]["value"])  # does not raise
