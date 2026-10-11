"""Unit tests for the ``session_factory`` seam (st-v058-byoa-21).

Spec: ``docs/specs/bring-your-own-app.md`` section C.3.

Every test maps 1:1 to a scenario in
``.meta/epics/epic-v058-bring-your-own-app/stories/
featcore-session-factory-seam-on-baseadapter-adapters-and-au.md``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class SfCategory(SQLModel, table=True):
    """A relation target, used for the FK filter scenario."""

    __tablename__ = "test_sf_category"

    id: int | None = Field(default=None, primary_key=True)
    label: str = ""


class SfWidget(SQLModel, table=True):
    """A parent model with inline children and an FK filter field."""

    __tablename__ = "test_sf_widget"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    category_id: int | None = Field(default=None, foreign_key="test_sf_category.id")


class SfPart(SQLModel, table=True):
    """Inline child of :class:`SfWidget`."""

    __tablename__ = "test_sf_part"

    id: int | None = Field(default=None, primary_key=True)
    widget_id: int | None = Field(default=None, foreign_key="test_sf_widget.id")
    sku: str = ""


class SfWidgetAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class SfCategoryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
async def sqlite_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


# ---------------------------------------------------------------------------
# Scenario: host session factory is used
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_host_session_factory_is_used(sqlite_engine: AsyncEngine) -> None:
    """
    Scenario: host session factory is used
      Given Admin(session_factory=host_sessionmaker)
      When  the user list page is requested
      Then  host_sessionmaker was called
    """
    # Given
    site.register(SfCategory, SfCategoryAdmin)
    maker = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    calls: list[int] = []

    def host_sessionmaker() -> Any:
        calls.append(1)
        return maker()

    app = FastAPI()
    admin = Admin(
        app,
        session_factory=host_sessionmaker,
        settings=HyperAdminSettings(create_tables=False),
    )
    admin.mount("/admin")

    # When
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/sfcategory")

    # Then
    assert response.status_code == 200
    assert calls, "host_sessionmaker was never called"
    # No engine was ever configured — the only seam available was the factory.
    assert admin.engine is None


# ---------------------------------------------------------------------------
# Scenario: legacy engine-only adapter works
# ---------------------------------------------------------------------------


class _LegacyEngineOnlyAdapter(BaseAdapter):
    """A third-party-style adapter using the pre-existing, engine-only constructor."""

    def __init__(self, model: Any, engine: Any) -> None:
        super().__init__(model, engine)

    async def get(self, pk: Any) -> Any:
        raise NotImplementedError

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        search_fields: list[str] | None = None,
    ) -> tuple[list[Any], int]:
        async with self._session() as session:
            result = await session.execute(sa_select(self.model))
            rows = list(result.scalars().all())
        return rows, len(rows)

    async def create(self, data: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        raise NotImplementedError

    async def delete(self, pk: Any) -> None:
        raise NotImplementedError

    async def get_related(self, pk: Any, field: str) -> list[Any]:
        raise NotImplementedError

    async def get_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    async def get_choices(
        self, field: str, q: str = "", limit: int = 50, offset: int = 0, **filters: Any
    ) -> list[Any]:
        raise NotImplementedError

    async def save_inline_rows(self, spec: Any, rows: list[dict[str, Any]], parent_pk: Any) -> None:
        raise NotImplementedError


@pytest.mark.anyio
async def test_legacy_engine_only_adapter_works(sqlite_engine: AsyncEngine) -> None:
    """
    Scenario: legacy engine-only adapter works
      Given a custom adapter calling super().__init__(model, engine)
      When  list() runs
      Then  rows are returned
    """
    # Given
    async with sqlite_engine.begin() as conn:
        await conn.execute(SfCategory.__table__.insert().values(label="a"))
        await conn.execute(SfCategory.__table__.insert().values(label="b"))
    adapter = _LegacyEngineOnlyAdapter(SfCategory, sqlite_engine)

    # When
    rows, total = await adapter.list()

    # Then
    assert total == 2
    assert {row.label for row in rows} == {"a", "b"}


# ---------------------------------------------------------------------------
# Scenario: neither engine nor factory
# ---------------------------------------------------------------------------


def test_neither_engine_nor_factory_raises_value_error() -> None:
    """
    Scenario: neither engine nor factory
      Given BaseAdapter(model) with neither argument
      When  it is constructed
      Then  ValueError is raised
    """
    # Given / When / Then
    with pytest.raises(ValueError, match="engine="):
        SQLModelAdapter(SfCategory)


# ---------------------------------------------------------------------------
# Scenario (review amendment): session_factory-only parent with inlines and an
# FK filter lists and saves without raising ValueError.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_session_factory_only_parent_with_inlines_and_fk_filter_lists(
    sqlite_engine: AsyncEngine,
) -> None:
    """
    Scenario: session_factory-only parent with inlines and an FK filter lists
      Given Admin(session_factory=...) with no engine=
        and a model with an inline and a list_filter on an FK field
      When  the list page is requested
      Then  the response is 200 (no ValueError from any adapter construction)
    """
    # Given
    async with sqlite_engine.begin() as conn:
        await conn.execute(SfCategory.__table__.insert().values(id=1, label="gadgets"))
        await conn.execute(SfWidget.__table__.insert().values(id=1, name="widget-1", category_id=1))
    maker = async_sessionmaker(sqlite_engine, expire_on_commit=False)

    site.register(SfCategory, SfCategoryAdmin)
    site.register(
        SfWidget,
        SfWidgetAdmin,
        options=AdminOptions(
            list_filter=["category_id"],
            inlines=[InlineModelSpec(model=SfPart, fk_field="widget_id")],
        ),
    )

    app = FastAPI()
    admin = Admin(app, session_factory=maker, settings=HyperAdminSettings(create_tables=False))
    admin.mount("/admin")

    # When
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/sfwidget")

    # Then — no ValueError bubbled up from constructing the FK-filter's target
    # adapter (core/discovery.py) via ``adapter.for_model`` instead of
    # ``adapter.engine``.
    assert response.status_code == 200


@pytest.mark.anyio
async def test_session_factory_only_adapter_saves_inline_rows(sqlite_engine: AsyncEngine) -> None:
    """
    Scenario: session_factory-only parent with inlines saves
      Given a SQLModelAdapter(SfWidget, session_factory=...) with no engine=
      When  save_inline_rows() creates a new SfPart row for an existing widget
      Then  the row is persisted, with no ValueError from the inline adapter
        construction (``for_model``, SDD C.3)
    """
    # Given
    async with sqlite_engine.begin() as conn:
        await conn.execute(SfWidget.__table__.insert().values(id=1, name="widget-1"))
    maker = async_sessionmaker(sqlite_engine, expire_on_commit=False)
    adapter = SQLModelAdapter(SfWidget, session_factory=maker)
    spec = InlineModelSpec(model=SfPart, fk_field="widget_id")

    # When
    await adapter.save_inline_rows(spec, [{"sku": "part-1"}], parent_pk=1)

    # Then
    async with maker() as session:
        result = await session.execute(sa_select(SfPart))
        parts = result.scalars().all()
    assert [p.sku for p in parts] == ["part-1"]
