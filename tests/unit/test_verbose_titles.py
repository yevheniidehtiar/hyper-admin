"""Readable names in titles, buttons and FK labels (st-ux-erp-11)."""

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


class VtLedger(SQLModel, table=True):
    __tablename__ = "vt_ledger"

    id: int | None = Field(default=None, primary_key=True)
    name: str


class VtJournalLine(SQLModel, table=True):
    __tablename__ = "vt_journal_line"

    id: int | None = Field(default=None, primary_key=True)
    ledger_id: int = Field(foreign_key="vt_ledger.id")
    memo: str


class VtHTTPLogEntry(SQLModel, table=True):
    __tablename__ = "vt_http_log"

    id: int | None = Field(default=None, primary_key=True)
    path: str


class VtLedgerAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    verbose_name = "Ledger book"


class VtJournalLineAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class VtHTTPLogEntryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(VtLedger, VtLedgerAdmin)
    site.register(VtJournalLine, VtJournalLineAdmin)
    site.register(VtHTTPLogEntry, VtHTTPLogEntryAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_title_and_button_use_the_verbose_names(client: TestClient) -> None:
    """
    Scenario: titles use the plural verbose name
      Given the JournalLine admin
      Then  the list title reads "Vt journal lines" and the button "Create vt journal line"
    """
    html = client.get("/admin/vtjournalline").text

    assert '<h1 class="ha-page-title">Vt journal lines</h1>' in html
    assert "Create vt journal line" in html
    assert "Create New" not in html


def test_declared_verbose_name_wins(client: TestClient) -> None:
    """
    Scenario: a declared verbose name is used
      Given an admin with verbose_name "Ledger book"
      When  its list and create pages render
      Then  they say "Ledger books" and "Create ledger book"
    """
    assert "Ledger books" in client.get("/admin/vtledger").text
    assert "Create ledger book" in client.get("/admin/vtledger/create").text


def test_leading_acronym_is_kept_in_the_button(client: TestClient) -> None:
    """
    Scenario: acronyms stay upper case
      Given a model named VtHTTPLogEntry
      When  its list renders
      Then  the title keeps HTTP upper case
    """
    html = client.get("/admin/vthttplogentry").text

    assert "Vt HTTP log entries" in html
    assert "Create vt HTTP log entry" in html


def test_fk_label_drops_the_id_suffix(client: TestClient) -> None:
    """
    Scenario: FK labels do not show the column suffix
      Given a model with a ledger_id foreign key
      When  its create form renders
      Then  the label reads "Ledger" with no "id"
    """
    html = client.get("/admin/vtjournalline/create").text

    assert "Ledger id" not in html
    assert ">Ledger<" in html or "Ledger<span" in html
