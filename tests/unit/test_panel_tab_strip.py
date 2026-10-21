"""Detail-page tab strip and panel state fragments (st-v056-dp-03).

Spec: ``docs/specs/detail-panels.md``; designs ``DetailPanel`` and
``PanelStates``. Renders ``detail.html`` through the real routes and asserts
the markup contract the E2E suite and consumers rely on: test ids, the
``hx-get`` on the panel element, the loading/error/forbidden states and the
``?tab=`` deep link. Also pins the ERP demo registration of ``pdf_stream_panel``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from starlette.responses import HTMLResponse, Response

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import PanelDef
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.panels import pdf_stream_panel

PDF_BYTES = b"%PDF-1.4\n%%EOF\n"


class TabOrder(SQLModel, table=True):
    __tablename__ = "test_tab_order"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    paid: bool = False


async def _history(request: Request, obj: Any) -> Response:
    return HTMLResponse(f"<p>history of {obj.title}</p>")


async def _refused(request: Request, obj: Any) -> Response:
    raise HTTPException(status_code=403)


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(PDF_BYTES)
    return path


def _client(pdf_path: Path, *, panels: bool = True) -> TestClient:
    class OrderAdmin(ModelAdmin):
        adapter_class = SQLModelAdapter
        options = AdminOptions(
            panels=[
                pdf_stream_panel(
                    slug="invoice",
                    label="Invoice",
                    icon="file-text",
                    path_resolver=lambda o: pdf_path,
                ),
                PanelDef(slug="history", label="History", handler=_history),
                PanelDef(slug="refused", label="Refused", handler=_refused),
                PanelDef(
                    slug="receipt", label="Receipt", handler=_history, enabled=lambda o: o.paid
                ),
            ]
            if panels
            else None
        )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all, tables=[TabOrder.__table__])
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        async with sessionmaker(engine, class_=AsyncSession)() as session:
            session.add(TabOrder(id=1, title="unpaid order", paid=False))
            session.add(TabOrder(id=2, title="paid order", paid=True))
            await session.commit()

    anyio.run(_setup)
    app = FastAPI()
    admin = Admin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="x" * 40),
    )
    site.register(TabOrder, OrderAdmin)
    admin.mount(path="/admin")
    return TestClient(app)


def _panel_div(html: str, slug: str) -> str:
    """Return the opening tag of the ``panel-body-{slug}`` element."""
    match = re.search(rf'<div class="ha-panel"[^>]*data-testid="panel-body-{slug}"[^>]*>', html)
    assert match, f"panel body for {slug!r} not rendered"
    return match.group(0)


def _is_hidden(tag: str) -> bool:
    """True when the opening ``tag`` carries the server-rendered ``hidden`` attribute."""
    return re.search(r"\shidden(?=[\s>])", tag) is not None


def _tab_a(html: str, slug: str) -> str:
    match = re.search(rf'<a class="ha-tab"[^>]*data-testid="panel-tab-{slug}"[^>]*>', html)
    assert match, f"tab for {slug!r} not rendered"
    return match.group(0)


def test_tab_strip_renders_details_then_enabled_panels_in_order(pdf_path: Path) -> None:
    """
    Scenario: detail page renders configured panel tabs
      Given panels invoice, history, refused and a paid-only receipt
      When  the user opens the unpaid order's detail page
      Then  the tab strip has Details first, then the enabled panels in declared order
      And   each tab carries its data-testid and controls its panel body
    """
    html = _client(pdf_path).get("/admin/taborder/1").text

    assert 'data-testid="panel-tabs"' in html
    assert 'role="tablist"' in html
    assert re.findall(r'data-testid="panel-tab-([a-z_-]+)"', html) == [
        "fields",
        "invoice",
        "history",
        "refused",
    ]
    assert 'data-testid="panel-tab-receipt"' not in html
    assert 'data-testid="panel-body-receipt"' not in html
    assert 'aria-controls="panel-invoice"' in _tab_a(html, "invoice")
    assert ">Details</a>" in html
    assert "Invoice</a>" in html
    # The icon is rendered next to the label
    assert (
        '<svg class="ha-icon ha-icon-sm"'
        in _tab_a(html, "invoice") + html.split(_tab_a(html, "invoice"))[1][:400]
    )


def test_panel_bodies_carry_hx_get_and_are_hidden_until_selected(pdf_path: Path) -> None:
    """
    Scenario: panel body lazy-loads when its tab becomes visible
      Given the detail page of order 1
      Then  each panel element (not the tab) carries hx-get to its render URL
      And   it triggers on "intersect once" (hidden panels never load up front)
      And   only the Details panel is visible on load
    """
    html = _client(pdf_path).get("/admin/taborder/1").text

    invoice = _panel_div(html, "invoice")
    assert 'hx-get="http://testserver/admin/taborder/1/panels/invoice"' in invoice
    assert 'hx-trigger="intersect once"' in invoice
    assert 'hx-swap="innerHTML"' in invoice
    assert 'aria-busy="true"' in invoice
    assert 'role="tabpanel"' in invoice
    assert 'aria-labelledby="panel-tab-invoice"' in invoice
    assert _is_hidden(invoice)

    fields = _panel_div(html, "fields")
    assert not _is_hidden(fields)
    assert "hx-get" not in fields
    assert 'aria-selected="true"' in _tab_a(html, "fields")
    assert 'aria-selected="false"' in _tab_a(html, "invoice")
    assert 'tabindex="-1"' in _tab_a(html, "invoice")
    assert "unpaid order" in html


def test_loading_state_has_skeleton_sr_text_and_error_template(pdf_path: Path) -> None:
    """
    Scenario: a panel shows the loading state until it answers, and an error state if it fails
      Given the detail page of order 1
      Then  each lazy panel holds skeleton lines and "Loading <label>" for screen readers
      And   a <template> with the error state whose Retry link is ?tab=<slug>
    """
    html = _client(pdf_path).get("/admin/taborder/1").text

    assert html.count('class="ha-skel"') == 3 * 3  # three lazy panels, three lines each
    assert "Loading Invoice" in html
    assert "Loading History" in html
    assert "<template data-panel-error>" in html
    assert 'data-testid="panel-error"' in html
    assert "Invoice didn't load." in html
    assert 'href="?tab=invoice" data-testid="panel-retry"' in html
    assert 'href="?tab=history" data-testid="panel-retry"' in html
    assert "The other tabs still work." in html
    # The no-JS fallback links straight to the panel URL
    assert '<noscript><a href="http://testserver/admin/taborder/1/panels/history">' in html


def test_tab_query_parameter_selects_the_panel_on_load(pdf_path: Path) -> None:
    """
    Scenario: ?tab=<slug> opens that panel on load
      When  the user opens /admin/taborder/1?tab=history
      Then  History is selected and visible, Details is hidden
      And   an unknown or disabled slug falls back to Details
    """
    client = _client(pdf_path)

    html = client.get("/admin/taborder/1?tab=history").text
    assert 'aria-selected="true"' in _tab_a(html, "history")
    assert 'tabindex="-1"' not in _tab_a(html, "history")
    assert 'aria-selected="false"' in _tab_a(html, "fields")
    assert not _is_hidden(_panel_div(html, "history"))
    assert _is_hidden(_panel_div(html, "fields"))
    assert 'tab: "history"' in html

    for query in ("?tab=nope", "?tab=receipt", "?tab=<script>"):
        html = client.get("/admin/taborder/1" + query).text
        assert 'aria-selected="true"' in _tab_a(html, "fields"), query
        assert 'tab: "fields"' in html, query
    assert (
        "<script>" not in client.get("/admin/taborder/1?tab=<script>").text.split("x-data")[1][:200]
    )


def test_detail_page_without_panels_renders_no_tab_strip(pdf_path: Path) -> None:
    """
    Scenario: admins without panels keep the plain detail layout
      Given a model registered without panels
      When  the user opens its detail page
      Then  there is no tab strip, no tabpanel and the field list sits in a plain card
    """
    html = _client(pdf_path, panels=False).get("/admin/taborder/1").text

    assert "panel-tabs" not in html
    assert "tabpanel" not in html
    assert "ha-card--tabbed" not in html
    assert '<div class="ha-card">' in html
    assert "unpaid order" in html
    assert 'data-testid="detail-fields"' in html


def test_document_viewer_iframe_is_named_after_the_panel_slug(pdf_path: Path) -> None:
    """
    Scenario: streaming panel returns the document viewer
      When  the Invoice panel body is requested
      Then  the viewer's frame carries data-testid="panel-iframe-invoice"
    """
    html = _client(pdf_path).get("/admin/taborder/1/panels/invoice").text

    assert 'data-testid="panel-pdf-viewer"' in html
    assert 'data-testid="panel-iframe-invoice"' in html
    assert 'src="http://testserver/admin/taborder/1/panels/invoice/stream"' in html


def test_forbidden_state_is_the_403_fragment(pdf_path: Path) -> None:
    """
    Scenario: panel handler raising HTTPException(403) surfaces a forbidden body
      When  the Refused panel body is requested
      Then  the forbidden state (and only it) is returned with status 403
    """
    response = _client(pdf_path).get("/admin/taborder/1/panels/refused")

    assert response.status_code == 403
    assert 'data-testid="panel-forbidden"' in response.text
    assert "view_taborder_panel_refused" in response.text
    assert "ha-skel" not in response.text
    assert "panel-error" not in response.text


def test_erp_invoice_admin_registers_the_pdf_stream_demo_panel() -> None:
    """
    Scenario: the ERP example ships the bundled PDF streaming demo
      Given examples/erp registers Invoice with pdf_stream_panel
      Then  the panel is "invoice", resolves to tests/_fixtures/sample.pdf
      And   is enabled for issued invoices only
    """
    from examples.erp.sales.admin import SAMPLE_PDF, InvoiceAdmin
    from examples.erp.sales.models import InvoiceStatus

    (panel,) = InvoiceAdmin.options.panels or []
    assert panel.slug == "invoice"
    assert panel.label == "Invoice"
    assert panel.icon == "file-text"
    assert SAMPLE_PDF.is_file()
    assert SAMPLE_PDF.read_bytes().startswith(b"%PDF-")
    assert panel.enabled is not None

    class _Invoice:
        def __init__(self, status: InvoiceStatus) -> None:
            self.status = status

    assert panel.enabled(_Invoice(InvoiceStatus.DRAFT)) is False
    assert panel.enabled(_Invoice(InvoiceStatus.SENT)) is True
    assert panel.enabled(_Invoice(InvoiceStatus.PAID)) is True
