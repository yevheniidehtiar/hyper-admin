"""Auth-less HyperAdmin app whose plugins are discovered through (faked) entry points.

Started by the ``plugin_hooks_base_url`` fixture in ``tests/e2e/test_plugin_hooks.py``.
Entry points: ``recording`` (records hooks, serves ``/admin/recording/events``),
``broken`` (raises from every hook, serves ``/admin/broken/logs``) and ``muted``
(disabled through ``disabled_plugins``). Registers one model, ``Widget``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from tests.e2e.apps.plugin_hook_doubles import BrokenPlugin, RecordingPlugin, install_entry_points

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class Widget(SQLModel, table=True):
    __tablename__ = "e2e_hook_widget"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class WidgetAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

install_entry_points(
    {"recording": RecordingPlugin(), "broken": BrokenPlugin()}, disabled_name="muted"
)
admin = Admin(
    app,
    engine=engine,
    settings=HyperAdminSettings(create_tables=False, secret_key="e2e-test-secret"),
    disabled_plugins=["muted"],
)
site.register(Widget, WidgetAdmin)
admin.mount(path="/admin")
