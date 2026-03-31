"""Integration test: 3-line zero-config demo verification (#372).

Verifies that ``Admin(app, engine=engine).mount("/admin")`` with
``auto_discover=True`` registers auto-discovered models with full CRUD.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.core.app import Admin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

# ── Test models ────────────────────────────────────────────────────────


class ZCColor(str, Enum):
    RED = "red"
    BLUE = "blue"


class ZCCategory(SQLModel, table=True):
    __tablename__ = "zc_categories"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)


class ZCProduct(SQLModel, table=True):
    __tablename__ = "zc_products"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)
    price: float = 0.0
    color: ZCColor = Field(default=ZCColor.RED)
    category_id: int | None = Field(default=None, foreign_key="zc_categories.id")
    created_at: datetime | None = Field(default_factory=datetime.now)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_registry():
    """Save and restore registry state to prevent leaking between tests."""
    saved = dict(site._registry)
    yield
    site._registry = saved


@pytest.fixture
def engine(tmp_path):
    """Create an async engine (sync fixture — registration doesn't need await)."""
    db_file = tmp_path / "test_zc.db"
    return create_async_engine(f"sqlite+aiosqlite:///{db_file}")


# ── Tests ──────────────────────────────────────────────────────────────


class TestZeroConfig:
    def test_auto_discover_registers_models(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        registered = {m.__name__ for m in site._registry}
        assert "ZCCategory" in registered
        assert "ZCProduct" in registered

    def test_auto_discover_false_skips_discovery(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=False, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        registered = {m.__name__ for m in site._registry}
        assert "ZCCategory" not in registered
        assert "ZCProduct" not in registered

    def test_explicit_registration_not_overwritten(self, engine) -> None:
        from hyperadmin.core.model import ModelAdmin
        from hyperadmin.core.options import AdminOptions

        custom_admin = type("CustomCategoryAdmin", (ModelAdmin,), {})
        custom_opts = AdminOptions(can_delete=False)
        site.register(ZCCategory, admin_class=custom_admin, options=custom_opts)

        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        admin_cls = site._registry[ZCCategory]
        assert admin_cls.options.can_delete is False

    def test_inferred_options_on_auto_registered_model(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        admin_cls = site._registry[ZCProduct]
        opts = admin_cls.options
        assert opts.list_display is not None
        assert "id" in opts.list_display
        assert "name" in opts.list_display

    @pytest.mark.anyio
    async def test_list_view_responds(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/zcproduct")
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_dashboard_responds(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/admin/")
            assert resp.status_code == 200

    def test_sidebar_includes_auto_discovered_models(self, engine) -> None:
        app = FastAPI()
        settings = HyperAdminSettings(auto_discover=True, create_tables=False)
        admin = Admin(app, engine=engine, settings=settings)
        admin.mount("/admin")

        nav_items = admin.templates.env.globals.get("nav_items", [])
        nav_names = {item["name"] for item in nav_items}
        assert any("ZCProduct" in n or "Zcproduct" in n for n in nav_names)
