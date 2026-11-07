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
      Then  they say "Ledger books" and "Create Ledger book"
    """
    assert "Ledger books" in client.get("/admin/vtledger").text
    assert "Create Ledger book" in client.get("/admin/vtledger/create").text


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


def test_view_with_a_plain_admin_object_falls_back_to_the_class_name() -> None:
    """
    Scenario: an admin object without verbose-name hooks keeps the humanised class name
      Given a dynamic view whose admin instance has no get_verbose_name (a ModelView)
      When  the verbose labels are built
      Then  the singular is the humanised class name and the plural is pluralised
    """
    from types import SimpleNamespace

    from hyperadmin.views.dynamic.base import DynamicModelViewBase

    # Given
    view = DynamicModelViewBase.__new__(DynamicModelViewBase)
    view.model = VtJournalLine
    view._admin_instance = SimpleNamespace()

    # When
    labels = view._verbose_labels()

    # Then
    assert labels["verbose_name"] == "Vt journal line"
    assert labels["verbose_name_plural"] == "Vt journal lines"


def test_no_camel_case_class_name_on_list_detail_create_and_bulk_pages(client: TestClient) -> None:
    """
    Scenario: no CamelCase class name reaches the rendered text
      Given a JournalLine record
      When  its list, detail and create pages render
      Then  none of their model labels contains the class name "VtJournalLine"
    """
    # Given
    client.post("/admin/vtledger/", data={"name": "L"})
    client.post("/admin/vtjournalline/", data={"ledger_id": "1", "memo": "m"})

    # When
    pages = [
        client.get("/admin/vtjournalline").text,
        client.get("/admin/vtjournalline/1").text,
        client.get("/admin/vtjournalline/create").text,
    ]

    # Then
    # (a record's own default ``__str__`` is "VtJournalLine (1)": not a model label)
    for html in pages:
        for label in (
            "VtJournalLine list",
            "VtJournalLine Detail",
            "Create New",
            "Create VtJournalLine",
        ):
            assert label not in html
    assert ">VtJournalLine<" not in pages[0]
    assert "Vt journal line list" in pages[0]
    assert "Vt journal line Detail | HyperAdmin" in pages[1]


def test_declared_name_is_not_lowercased_and_may_equal_the_class_name() -> None:
    """
    Scenario: declared names are used as given
      Given admins declaring "Acme invoice", the bare class name and a lazy name
      When  the verbose labels are built
      Then  the declared text is kept and only derived names are lowercased
    """
    from hyperadmin.i18n.loader import gettext_lazy
    from hyperadmin.views.dynamic.base import DynamicModelViewBase

    def labels(admin_cls: type[ModelAdmin]) -> dict[str, str]:
        view = DynamicModelViewBase.__new__(DynamicModelViewBase)
        view.model = VtJournalLine
        view._admin_instance = admin_cls(VtJournalLine)
        return view._verbose_labels()

    class Acme(ModelAdmin):
        verbose_name = "Acme invoice"

    class SameAsClass(ModelAdmin):
        verbose_name = "VtJournalLine"

    class Lazy(ModelAdmin):
        verbose_name = gettext_lazy("Rechnung")

    assert labels(Acme)["verbose_name_lower"] == "Acme invoice"
    assert labels(SameAsClass)["verbose_name"] == "VtJournalLine"
    assert labels(Lazy)["verbose_name_lower"] == "Rechnung"
