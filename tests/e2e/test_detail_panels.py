"""End-to-end tests for detail-page panels and the tab strip (v0.5.6, st-v056-dp-03).

Spec: ``docs/specs/detail-panels.md`` — one test per BDD scenario, named after
it. Designs: ``docs/design/system/components/DetailPanel`` and ``PanelStates``.
Inline ``# Given / # When / # Then`` comments are mandatory (BDD conventions).

Selectors follow ``CLAUDE.md`` (E2E Selector Convention):
``get_by_role`` > ``get_by_label`` > ``get_by_text`` > ``get_by_test_id``.
``ha-*`` CSS classes are styling-only and never used as selectors.

The companion app (``tests.e2e.apps.detail_panels``) registers an ``Order``
with an Invoice (PDF stream), History (HTML), Refused (403) and Receipt
(paid-only) panel, the superuser ``alice`` and ``bob`` who may open History only.
The slug-collision scenario is a registration-time ``ValueError`` and lives in
``tests/unit/test_panels.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from playwright.sync_api import Page, Request, expect

from tests.e2e.conftest import _spawn_uvicorn, _terminate

ORDER_DETAIL = "/admin/order/1"


@pytest.fixture
def panels_base_url(e2e_port: int) -> Iterator[str]:
    """Start the detail-panels app (:mod:`tests.e2e.apps.detail_panels`) and yield its base URL."""
    proc, base = _spawn_uvicorn("tests.e2e.apps.detail_panels", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _panel_requests(page: Page, slug: str) -> list[Request]:
    """Record every request for the ``slug`` panel body (not its ``/stream`` sub-route)."""
    seen: list[Request] = []
    page.on(
        "request",
        lambda r: seen.append(r) if r.url.endswith(f"/panels/{slug}") else None,
    )
    return seen


def test_detail_page_renders_configured_panel_tabs(page: Page, panels_base_url: str) -> None:
    """
    Scenario: detail page renders configured panel tabs
      Given AdminOptions(panels=[PanelDef(slug="invoice", label="Invoice", handler=...)])
      When  the user opens /admin/order/1
      Then  the page has a tab strip with one tab "Invoice"
      And   the panel's hx-get is "/admin/order/1/panels/invoice"
    """
    # Given alice is signed in
    _login(page, panels_base_url)

    # When she opens the detail page of the unpaid order
    page.goto(panels_base_url + ORDER_DETAIL)

    # Then the tab strip lists Details first, then the enabled panels in declared order
    tabs = page.get_by_test_id("panel-tabs")
    expect(tabs).to_be_visible()
    expect(tabs.get_by_role("tab")).to_have_text(["Details", "Invoice", "Refused", "History"])
    expect(tabs.get_by_role("tab", name="Details")).to_have_attribute("aria-selected", "true")
    # And the Receipt tab is not rendered at all: the order is unpaid (enabled predicate)
    expect(page.get_by_role("tab", name="Receipt")).to_have_count(0)
    # And the field list is the visible panel
    expect(page.get_by_test_id("panel-body-fields")).to_be_visible()
    expect(page.get_by_test_id("panel-body-fields")).to_contain_text("unpaid")

    # And the Invoice tab controls a panel body that lazy-loads the panel URL
    invoice_tab = page.get_by_test_id("panel-tab-invoice")
    expect(invoice_tab).to_have_attribute("aria-controls", "panel-invoice")
    invoice_body = page.get_by_test_id("panel-body-invoice")
    expect(invoice_body).to_have_attribute("hx-get", re.compile(r"/admin/order/1/panels/invoice$"))
    expect(invoice_body).to_have_attribute("hx-trigger", "intersect once")
    expect(invoice_body).to_be_hidden()


def test_panel_body_lazy_loads_on_tab_click(page: Page, panels_base_url: str) -> None:
    """
    Scenario: panel body lazy-loads when its tab becomes visible
      Given the same configuration
      When  the user clicks the "History" tab
      Then  GET /admin/order/1/panels/history is issued exactly once
      And   the response body replaces the tab content area
    """
    # Given alice is on the detail page and no panel has been requested yet
    _login(page, panels_base_url)
    history_requests = _panel_requests(page, "history")
    page.goto(panels_base_url + ORDER_DETAIL)
    page.wait_for_load_state("networkidle")
    assert history_requests == []
    expect(page.get_by_test_id("panel-body-history")).to_have_attribute("aria-busy", "true")

    # When she clicks the History tab
    page.get_by_role("tab", name="History").click()

    # Then the handler's HTML replaces the skeleton in the History panel
    history = page.get_by_test_id("panel-body-history")
    expect(history).to_be_visible()
    expect(history.get_by_test_id("history-body")).to_have_text(
        "Order unpaid was created by alice."
    )
    expect(history).not_to_have_attribute("aria-busy", "true")
    expect(page.get_by_role("tab", name="History")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_test_id("panel-body-fields")).to_be_hidden()

    # And leaving and coming back does not request it again
    page.get_by_role("tab", name="Details").click()
    expect(history).to_be_hidden()
    page.get_by_role("tab", name="History").click()
    expect(history.get_by_test_id("history-body")).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert len(history_requests) == 1


def test_streaming_panel_serves_inline_pdf(page: Page, panels_base_url: str) -> None:
    """
    Scenario: streaming panel returns Content-Disposition inline
      Given a PDF panel returning StreamingResponse with media_type="application/pdf"
      When  the user clicks the tab
      Then  the tab content is replaced with an <iframe src="/admin/order/1/panels/invoice/stream">
      And   GET on that stream URL returns "Content-Disposition: inline" and the PDF bytes
    """
    # Given alice is on the detail page
    _login(page, panels_base_url)
    page.goto(panels_base_url + ORDER_DETAIL)

    # When she clicks the Invoice tab
    page.get_by_role("tab", name="Invoice").click()

    # Then the document viewer with its frame replaces the skeleton
    viewer = page.get_by_test_id("panel-body-invoice").get_by_test_id("panel-pdf-viewer")
    expect(viewer).to_be_visible()
    expect(viewer).to_contain_text("sample.pdf")
    frame = page.get_by_test_id("panel-iframe-invoice")
    expect(frame).to_be_visible()
    expect(frame).to_have_attribute("src", re.compile(r"/admin/order/1/panels/invoice/stream$"))
    expect(viewer.get_by_role("link", name=re.compile("Open in new tab"))).to_have_attribute(
        "target", "_blank"
    )

    # And the stream URL serves the PDF inline
    stream_url = frame.get_attribute("src")
    assert stream_url is not None
    response = page.request.get(stream_url)
    assert response.status == HTTPStatus.OK
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.body().startswith(b"%PDF-")

    # And the Download link forces a download of the same bytes
    download = page.request.get(f"{stream_url}?download=1")
    assert download.headers["content-disposition"].startswith("attachment")


def test_panel_handler_403_surfaces_forbidden_body(page: Page, panels_base_url: str) -> None:
    """
    Scenario: panel handler raising HTTPException(403) surfaces a forbidden body
      Given a panel handler that raises HTTPException(403)
      When  the user clicks the tab
      Then  the tab body renders the standard 403 partial
      And   sibling tabs remain functional
    """
    # Given alice is on the detail page
    _login(page, panels_base_url)
    page.goto(panels_base_url + ORDER_DETAIL)

    # When she clicks the Refused tab
    page.get_by_role("tab", name="Refused").click()

    # Then the forbidden state renders inside that panel only
    refused = page.get_by_test_id("panel-body-refused")
    forbidden = refused.get_by_test_id("panel-forbidden")
    expect(forbidden).to_be_visible()
    expect(forbidden).to_contain_text("You don't have access to this panel.")
    expect(forbidden).to_contain_text("view_order_panel_refused")
    expect(refused).not_to_have_attribute("aria-busy", "true")
    expect(page.get_by_test_id("panel-tabs")).to_be_visible()

    # And the sibling History tab still loads its body
    page.get_by_role("tab", name="History").click()
    expect(page.get_by_test_id("history-body")).to_be_visible()
    expect(refused).to_be_hidden()
    # And the Details tab still shows the record
    page.get_by_role("tab", name="Details").click()
    expect(page.get_by_test_id("panel-body-fields")).to_contain_text("unpaid")


def test_permission_codename_gates_panel_access(page: Page, panels_base_url: str) -> None:
    """
    Scenario: permission codename gates panel access
      Given user lacks "view_order_panel_invoice"
      When  GET /admin/order/1/panels/invoice is issued
      Then  response is 403
    """
    # Given bob, who holds view_order and view_order_panel_history only, is signed in
    _login(page, panels_base_url, "bob")
    page.goto(panels_base_url + ORDER_DETAIL)

    # Then the tab strip omits the panels he may not open
    expect(page.get_by_test_id("panel-tabs").get_by_role("tab")).to_have_text(
        ["Details", "History"]
    )

    # When he requests the Invoice panel URL directly
    response = page.request.get(f"{panels_base_url}{ORDER_DETAIL}/panels/invoice")

    # Then it is refused, while the panel he holds still answers
    assert response.status == HTTPStatus.FORBIDDEN
    stream = page.request.get(f"{panels_base_url}{ORDER_DETAIL}/panels/invoice/stream")
    assert stream.status == HTTPStatus.FORBIDDEN
    history = page.request.get(f"{panels_base_url}{ORDER_DETAIL}/panels/history")
    assert history.status == HTTPStatus.OK
    assert "created by alice" in history.text()


def test_enabled_predicate_shows_the_tab_for_matching_records_only(
    page: Page, panels_base_url: str
) -> None:
    """
    Scenario: a tab hidden by its enabled predicate is rendered only where the predicate holds
      Given a Receipt panel enabled for paid orders only
      When  the user opens the paid order's detail page
      Then  the Receipt tab is rendered and loads its body on click
      And   the unpaid order's page has no such tab
    """
    # Given alice opens the paid order
    _login(page, panels_base_url)
    page.goto(f"{panels_base_url}/admin/order/2")

    # When she clicks the Receipt tab
    receipt_tab = page.get_by_role("tab", name="Receipt")
    expect(receipt_tab).to_be_visible()
    receipt_tab.click()

    # Then the panel body loads
    expect(page.get_by_test_id("receipt-body")).to_have_text("Receipt for paid")

    # And the unpaid order has no Receipt tab and answers 404 for its URL
    page.goto(panels_base_url + ORDER_DETAIL)
    expect(page.get_by_role("tab", name="Receipt")).to_have_count(0)
    response = page.request.get(f"{panels_base_url}{ORDER_DETAIL}/panels/receipt")
    assert response.status == HTTPStatus.NOT_FOUND


def test_tab_query_parameter_selects_a_panel_on_load(page: Page, panels_base_url: str) -> None:
    """
    Scenario: ?tab=<slug> opens that panel on page load
      Given the same configuration
      When  the user opens /admin/order/1?tab=history
      Then  the History tab is selected and its body is loaded without a click
      And   an unknown slug falls back to the Details tab
    """
    # Given alice is signed in
    _login(page, panels_base_url)

    # When she opens the detail page with ?tab=history (what the error state's Retry link does)
    page.goto(f"{panels_base_url}{ORDER_DETAIL}?tab=history")

    # Then History is the selected tab and its body loaded
    expect(page.get_by_role("tab", name="History")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_test_id("history-body")).to_be_visible()
    expect(page.get_by_test_id("panel-body-fields")).to_be_hidden()

    # And an unknown slug falls back to Details
    page.goto(f"{panels_base_url}{ORDER_DETAIL}?tab=nope")
    expect(page.get_by_role("tab", name="Details")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_test_id("panel-body-fields")).to_be_visible()


def test_arrow_keys_move_between_tabs(page: Page, panels_base_url: str) -> None:
    """
    Scenario: arrow keys move the selection along the tab strip
      Given the Details tab has focus
      When  the user presses ArrowRight, then End, then ArrowRight
      Then  the selection moves to Invoice, History and wraps back to Details
    """
    # Given alice is on the detail page with the Details tab focused
    _login(page, panels_base_url)
    page.goto(panels_base_url + ORDER_DETAIL)
    page.get_by_role("tab", name="Details").focus()

    # When she presses ArrowRight
    page.keyboard.press("ArrowRight")
    # Then Invoice is selected and focused, and its panel is the visible one
    expect(page.get_by_role("tab", name="Invoice")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_role("tab", name="Invoice")).to_be_focused()
    expect(page.get_by_test_id("panel-body-invoice")).to_be_visible()

    # When she presses End, then ArrowRight
    page.keyboard.press("End")
    expect(page.get_by_role("tab", name="History")).to_have_attribute("aria-selected", "true")
    page.keyboard.press("ArrowRight")
    # Then the selection wraps around to Details
    expect(page.get_by_role("tab", name="Details")).to_have_attribute("aria-selected", "true")
    expect(page.get_by_test_id("panel-body-fields")).to_be_visible()
