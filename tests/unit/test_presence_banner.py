"""The edit page renders the presence banner shell only when realtime is on (story #328)."""

from __future__ import annotations

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
from hyperadmin.realtime import RealtimeSettings


class PresenceNote(SQLModel, table=True):
    __tablename__ = "test_presence_note"
    id: int | None = Field(default=None, primary_key=True)
    title: str


class PresenceNoteAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean_registry():
    site._registry = {}
    yield
    site._registry = {}


def _client(realtime: RealtimeSettings | None) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            session.add(PresenceNote(title="Hello"))
            await session.commit()

    anyio.run(setup)
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        realtime=realtime,
    )
    site.register(PresenceNote, PresenceNoteAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


def test_edit_page_has_hidden_presence_banner_when_realtime_enabled() -> None:
    html = _client(RealtimeSettings()).get("/admin/presencenote/1/edit").text

    assert 'data-testid="presence-banner"' in html
    assert 'data-presence-model="presencenote"' in html
    assert 'data-presence-pk="1"' in html
    assert 'data-presence-mode="editing"' in html
    assert "hidden" in html.split('data-testid="presence-banner"')[0].rsplit("<div", 1)[1]


def test_edit_page_has_no_presence_banner_without_realtime() -> None:
    html = _client(None).get("/admin/presencenote/1/edit").text

    assert "presence-banner" not in html
