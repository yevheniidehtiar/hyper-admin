"""Upstream-readiness qualification suite: ten checks against ``examples/full-demo``.

Each test maps to one acceptance row of ``epic-upstream-readiness`` (H2, H3, H4, H5, H6,
H12, H13, H14, H15, H20) and drives the umbrella example app end to end, so a green run
means the framework's generic capabilities work together, not just one by one. Run with
``poe test:e2e:qualification``.

The app (``tests.e2e.apps.full_demo`` -> ``examples/full-demo/main.py``) seeds ``alice`` and
``bob`` (superusers, user keys 1 and 2) and ``viewer`` (group ``Viewers``: view/change
Order, view Invoice), all with password ``secret123``; orders ORD-1..ORD-5 (alice owns 1, 3
and 5; ORD-3 is locked); suppliers 42/43/44; and 2025 order items for the sales report.

Selectors follow ``CLAUDE.md``: role > label > text > ``data-testid``.
"""

from __future__ import annotations

import csv
import io
import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from tests.e2e.conftest import csrf_headers

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

ORDER_LIST = "/admin/order"


@pytest.fixture
def full_demo_base_url(start_server: Callable[..., str]) -> str:
    """Start the umbrella app (:mod:`tests.e2e.apps.full_demo`) and yield its base URL."""
    return start_server("tests.e2e.apps.full_demo", extra_env={"E2E_TESTING": "1"})


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _row_numbers(page: Page) -> list[str]:
    """Order numbers (``ORD-n``) of the rows in the list, in order."""
    return [
        re.search(r"ORD-\d+", row.inner_text()).group()  # type: ignore[union-attr]
        for row in page.get_by_test_id("list-row").all()
    ]


def test_h2_inline_row_error_highlight(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: a nested formset save with one failing child highlights that row only
      Given ORD-1 with two order items
      When  alice sets the second item's quantity to 0 and saves
      Then  the second inline row is marked invalid with its error
      And   the first row is not
    """
    # Given alice on ORD-1's edit form, which lists two items
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}{ORDER_LIST}/1/edit")
    first = page.get_by_test_id("inline-orderitem-row-0")
    second = page.get_by_test_id("inline-orderitem-row-1")
    expect(second).to_be_visible()

    # When she makes the second item invalid and saves
    second.get_by_label("Quantity").fill("0")
    page.get_by_role("button", name="Update").click()

    # Then only that row carries the error markers
    expect(second).to_have_attribute("aria-invalid", "true")
    expect(page.get_by_test_id("inline-orderitem-row-1-error")).to_be_attached()
    expect(page.get_by_test_id("orderitem-1-quantity-errors")).to_be_visible()
    # And the valid row stays unmarked
    expect(first).not_to_have_attribute("aria-invalid", "true")
    expect(page.get_by_test_id("inline-orderitem-row-0-error")).to_have_count(0)


def test_h3_bulk_action_per_row_outcome(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: a bulk action over 5 rows where 1 fails reports each row's outcome
      Given five orders, one of them locked
      When  alice selects all five and runs Archive
      Then  the outcome lists four Done rows and one Forbidden row
      And   the failed row is offered for retry
    """
    # Given the order list with five rows
    _login(page, full_demo_base_url)
    page.goto(full_demo_base_url + ORDER_LIST)
    expect(page.get_by_test_id("list-row")).to_have_count(5)

    # When she selects every row and runs the Archive action
    page.get_by_role("checkbox", name="Select all rows on this page").check()
    expect(page.get_by_test_id("bulk-count")).to_have_text("5 selected")
    page.get_by_label("Action for selected rows").select_option("archive")
    page.get_by_role("button", name="Run").click()

    # Then four rows are done and the locked ORD-3 (id 3) is not
    result = page.get_by_test_id("bulk-result")
    expect(result.get_by_test_id("bulk-result-row")).to_have_count(5)
    for pk in (1, 2, 4, 5):
        expect(result.get_by_test_id(f"bulk-result-status-{pk}")).to_have_text("Done")
    expect(result.get_by_test_id("bulk-result-status-3")).to_have_text("Forbidden")
    expect(result.get_by_role("status")).to_have_text("4 of 5 rows done. 1 not allowed.")
    # And only that row can be retried
    expect(result.get_by_role("button", name="Retry failures (1)")).to_be_visible()


def test_h4_detail_panels_with_pdf(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: the order detail page exposes Invoice, History and Transitions panels
      Given alice on /admin/order/1
      Then  the tab strip lists the three panels
      When  she opens Invoice
      Then  the sample PDF is streamed inline in a frame
    """
    # Given / When alice opens the detail page
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}{ORDER_LIST}/1")

    # Then the panels are tabs next to Details
    for name in ("Invoice", "History", "Transitions"):
        expect(page.get_by_role("tab", name=name)).to_be_visible()

    # When she opens History and Transitions, their handlers' HTML replaces the skeleton
    page.get_by_role("tab", name="History").click()
    expect(page.get_by_test_id("history-body")).to_have_text("Order ORD-1 was created.")
    page.get_by_role("tab", name="Transitions").click()
    expect(page.get_by_test_id("transitions-body")).to_contain_text("ORD-1")

    # And Invoice streams the PDF inline
    page.get_by_role("tab", name="Invoice").click()
    frame = page.get_by_test_id("panel-iframe-invoice")
    expect(frame).to_be_visible()
    stream_url = frame.get_attribute("src")
    assert stream_url is not None
    response = page.request.get(stream_url)
    assert response.ok
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline")
    assert response.body().startswith(b"%PDF-")


def test_h5_list_filter_by_owner(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: IsOwnerFilter restricts the list to the signed-in user's orders
      Given ORD-1, 3 and 5 belong to alice, ORD-2 and 4 to bob
      When  each of them turns on "Mine only"
      Then  they see exactly their own orders
    """
    for username, expected in (("alice", ["ORD-1", "ORD-3", "ORD-5"]), ("bob", ["ORD-2", "ORD-4"])):
        # Given the user on the unfiltered list
        _login(page, full_demo_base_url, username)
        page.goto(full_demo_base_url + ORDER_LIST)
        expect(page.get_by_test_id("list-row")).to_have_count(5)

        # When they switch "Mine only" on and apply
        page.get_by_test_id("filter-is_owner").check()
        with page.expect_response(lambda r: "is_owner=1" in r.url):
            page.get_by_test_id("filter-apply-btn").click()

        # Then only their orders remain
        expect(page.get_by_test_id("list-row")).to_have_count(len(expected))
        assert _row_numbers(page) == expected
        page.context.clear_cookies()


def test_h6_dependent_fk_autocomplete_and_popup(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: variants narrow by the chosen supplier and "+" creates a supplier inline
      Given the product form, where variant depends on supplier
      When  alice picks supplier 43
      Then  only that supplier's variants are offered
      When  she adds a new supplier through the "+" popup
      Then  it is selected in the supplier field
    """
    # Given alice on the product create form
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}/admin/product/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    # When she picks supplier 43 (Acme Packaging)
    page.get_by_test_id("autocomplete-select-supplier_id").select_option("43")

    # Then the variant list holds only Red
    variants = page.get_by_test_id("autocomplete-select-variant_id")
    expect(variants.locator("option")).to_have_text(["Red"])

    # When she creates a supplier from the "+" popup
    page.get_by_role("button", name="Add supplier").click()
    popup = page.get_by_test_id("popup-form")
    popup.get_by_label("Name").fill("Zed Corp")
    popup.get_by_label("City").fill("Utrecht")
    popup.get_by_role("button", name="Save and select").click()

    # Then the new supplier is selected, labelled with the product form's display template
    expect(page.get_by_test_id("popup-form")).to_have_count(0)
    select = page.get_by_test_id("autocomplete-select-supplier_id")
    expect(select.locator("option:checked")).to_have_text("Zed Corp — Utrecht")


def test_h12_filter_sidebar_and_saved_view(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: the sidebar combines date-range, multi-FK and boolean filters and saves a view
      Given five orders
      When  alice sets From 2025-07-01, picks two suppliers and "Paid: No", then applies
      Then  the body swaps over HTMX to the two matching orders
      When  she saves the filters as "Backlog"
      Then  the view is listed and loading it later restores the same rows
    """
    # Given the unfiltered list
    _login(page, full_demo_base_url)
    page.goto(full_demo_base_url + ORDER_LIST)
    expect(page.get_by_test_id("list-row")).to_have_count(5)

    # When she fills the three filters and applies
    page.get_by_test_id("filter-created_on-gte").fill("2025-07-01")
    sidebar = page.get_by_test_id("filter-supplier_id")
    sidebar.get_by_label("Acme Packaging").check()
    sidebar.get_by_label("Brabant Bakkerij").check()
    page.get_by_test_id("filter-paid").get_by_label("No").check()
    with page.expect_response(
        lambda r: "supplier_id__in=" in r.url and r.request.method == "GET"
    ) as response_info:
        page.get_by_test_id("filter-apply-btn").click()

    # Then only the tbody fragment came back, with the two orders that match all three
    assert response_info.value.text().lstrip().startswith("<tbody")
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    assert _row_numbers(page) == ["ORD-4", "ORD-5"]

    # When she saves these filters as a named view. The sidebar's hidden querystring is
    # rendered with the page and not refreshed by the tbody swap, so reload the pushed URL
    # first (reported upstream; drop the reload when the swap refreshes it).
    page.reload()
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    page.get_by_test_id("save-view-btn").click()
    page.get_by_label("Name").fill("Backlog")
    page.get_by_role("button", name="Save view").last.click()
    view = page.get_by_test_id("saved-views").get_by_role("link", name="Backlog")
    expect(view).to_be_visible()

    # Then opening the plain list and clicking the view restores the filtered rows
    page.goto(full_demo_base_url + ORDER_LIST)
    expect(page.get_by_test_id("list-row")).to_have_count(5)
    page.get_by_test_id("saved-views").get_by_role("link", name="Backlog").click()
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    assert _row_numbers(page) == ["ORD-4", "ORD-5"]


def test_h13_jpeg_upload_thumbnail(page: Page, full_demo_base_url: str, tmp_path: Path) -> None:
    """
    Scenario: a JPEG uploaded on a product renders as a thumbnail in the list
      Given the product create form with a cover image field
      When  alice uploads a JPEG and saves
      Then  the product list shows the cover as an image
    """
    from PIL import Image

    jpeg = tmp_path / "cover.jpg"
    Image.new("RGB", (320, 200), "teal").save(jpeg, "JPEG")

    # Given the create form
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}/admin/product/create")

    # When she uploads the JPEG and saves
    page.get_by_label("Name").fill("Gizmo")
    page.get_by_test_id("cover_image-file-input").set_input_files(str(jpeg))
    page.get_by_role("button", name="Create").click()
    expect(page.get_by_test_id("model-form")).to_have_count(0)

    # Then the list row shows a thumbnail
    page.goto(f"{full_demo_base_url}/admin/product")
    row = page.get_by_test_id("list-row").filter(has_text="Gizmo")
    expect(row.get_by_role("img")).to_be_visible(timeout=2000)


def _download(page: Page, slug: str, kind: str) -> bytes:
    page.get_by_test_id("report-export").get_by_text("Export", exact=True).click()
    with page.expect_download() as info:
        page.get_by_test_id(f"report-export-{kind}").click()
    assert info.value.suggested_filename == f"{slug}.{kind}"
    path = info.value.path()
    assert path is not None
    return path.read_bytes()


def test_h14_olap_report_csv_xlsx(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: sales by SKU x month, regrouped by quarter, exports to CSV and XLSX
      Given the "Sales by SKU" report
      Then  SKUs are rows and months are columns
      When  alice switches the period to quarter
      Then  the columns are quarters
      And   the CSV and XLSX exports carry the same SKUs
    """
    # Given / When the report page is opened
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}/admin/reports/sales-by-sku/")
    grid = page.get_by_test_id("report-grid")

    # Then months are the columns
    expect(grid.get_by_role("columnheader", name="2025-01")).to_be_visible()
    expect(grid.get_by_role("row", name=re.compile("^WIDGET"))).to_be_visible()

    # When she regroups by quarter
    page.get_by_test_id("report-period").get_by_role("link", name="Quarter").click()

    # Then quarters replace the months
    expect(grid.get_by_role("columnheader", name="Q1 2025")).to_be_visible()
    expect(grid.get_by_role("columnheader", name="2025-01")).to_have_count(0)

    # And both exports stream the dataset
    rows = list(csv.reader(io.StringIO(_download(page, "sales-by-sku", "csv").decode("utf-8-sig"))))
    assert {"WIDGET", "GADGET", "GIZMO"} <= {cell for row in rows for cell in row}
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(_download(page, "sales-by-sku", "xlsx")))
    values = {c.value for sheet in workbook.worksheets for row in sheet.iter_rows() for c in row}
    assert {"WIDGET", "GADGET", "GIZMO"} <= values


def test_h15_chart_bound_to_report(page: Page, full_demo_base_url: str) -> None:
    """
    Scenario: the same dataset is charted from the report
      Given the "Sales by SKU" report
      When  alice opens it
      Then  an SVG chart titled after the report reads out the grid's numbers
    """
    # Given / When the report page is opened
    _login(page, full_demo_base_url)
    page.goto(f"{full_demo_base_url}/admin/reports/sales-by-sku/")

    # Then the chart frame is lazy-loaded next to the grid
    frame = page.get_by_test_id("chart-frame").filter(
        has=page.get_by_role("heading", name="Sales by SKU", level=3)
    )
    svg = frame.get_by_test_id("chart-sales-by-sku")
    expect(svg).to_be_visible()
    expect(svg).to_have_accessible_name("Sales by SKU")
    # And a January point carries the same numbers as the grid's 2025-01 column
    point = svg.get_by_role("img", name=re.compile(r"^2025-01: .*GADGET 70.*WIDGET 100"))
    expect(point).to_have_count(1)
    expect(page.get_by_test_id("report-grid")).to_be_visible()


def test_h20_matrix_flips_view_not_edit(
    page: Page, browser: Browser, full_demo_base_url: str
) -> None:
    """
    Scenario: revoking change_order in the permission matrix makes a role view-only
      Given viewer, whose Viewers group may view and change orders
      When  alice unchecks "change order" for Viewers in the matrix and saves
      Then  viewer can still open an order's detail page
      And   the edit form and PUT answer 403
    """
    viewer_context = browser.new_context()
    viewer = viewer_context.new_page()
    try:
        # Given viewer can edit order 1 before the flip
        _login(viewer, full_demo_base_url, "viewer")
        before = viewer.goto(f"{full_demo_base_url}{ORDER_LIST}/1/edit")
        assert before is not None
        assert before.status == 200

        # When alice revokes change_order for Viewers
        _login(page, full_demo_base_url)
        page.goto(f"{full_demo_base_url}/admin/permissions-matrix/")
        page.get_by_test_id("pmatrix-group-select").select_option(label="Viewers")
        change = page.get_by_test_id("pmatrix-cell-order-change_order")
        expect(change).to_be_checked()
        change.uncheck()
        expect(page.get_by_test_id("pmatrix-unsaved-count")).to_have_text("1 unsaved change")
        with page.expect_response(
            lambda r: r.url.endswith("/save") and r.request.method == "POST"
        ) as saved:
            page.get_by_test_id("pmatrix-save-btn").click()
        assert saved.value.status == 200, saved.value.text()
        expect(page.get_by_test_id("pmatrix-saved-banner")).to_contain_text("1 change for Viewers.")

        # Then viewer still sees the detail page
        viewer.goto(f"{full_demo_base_url}{ORDER_LIST}/1")
        expect(viewer.get_by_test_id("detail-fields")).to_be_visible()
        # And editing is refused on the form and on the write endpoint
        edit = viewer.goto(f"{full_demo_base_url}{ORDER_LIST}/1/edit")
        assert edit is not None
        assert edit.status == 403
        viewer.goto(full_demo_base_url + ORDER_LIST)
        put = viewer.request.put(
            f"{full_demo_base_url}{ORDER_LIST}/1",
            headers=csrf_headers(viewer),
            form={"number": "edited", "created_on": "2026-01-05"},
        )
        assert put.status == 403
    finally:
        viewer_context.close()
