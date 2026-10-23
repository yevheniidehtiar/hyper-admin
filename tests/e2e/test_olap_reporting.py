"""E2E: OLAP-style report pages, exports and permission gating (st-v054-olap-04).

Runs against :mod:`tests.e2e.apps.olap_reporting`: generic Order data, no consumer schema.
Filter assertions are out of scope until filters ship. Uses accessibility-first selectors
per CLAUDE.md E2E Selector Convention.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _download_text(page: Page, base_url: str, slug: str, kind: str) -> bytes:
    """Click the export menu entry ``kind`` ('csv' or 'xlsx') and return the file bytes."""
    page.get_by_test_id("report-export").get_by_text("Export", exact=True).click()
    with page.expect_download() as info:
        page.get_by_test_id(f"report-export-{kind}").click()
    download = info.value
    assert download.suggested_filename == f"{slug}.{kind}"
    path = download.path()
    assert path is not None
    return path.read_bytes()


def test_report_registers_in_admin_nav(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: a registered report is listed in the admin sidebar and opens."""
    # Given three reports are registered and superuser alice is signed in
    _login(page, olap_reporting_base_url)

    # When she looks at the sidebar
    sidebar = page.get_by_test_id("sidebar")

    # Then each report has an entry under "Reports"
    expect(sidebar.get_by_test_id("nav-report-olap-by-product")).to_be_visible()
    expect(sidebar.get_by_test_id("nav-report-olap-by-month")).to_be_visible()

    # And following an entry opens that report's page
    sidebar.get_by_test_id("nav-report-olap-by-product").click()
    expect(page).to_have_url(f"{olap_reporting_base_url}/admin/reports/olap-by-product/")
    expect(page.get_by_role("heading", name="Revenue by product", level=1)).to_be_visible()


def test_sum_aggregate_renders_grid(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: a sum aggregate over one row group renders a grid with totals."""
    # Given a report of revenue per product
    _login(page, olap_reporting_base_url)

    # When the report page is opened
    page.goto(f"{olap_reporting_base_url}/admin/reports/olap-by-product/")

    # Then each product is a row carrying its summed revenue
    grid = page.get_by_test_id("report-grid")
    expect(grid).to_be_visible()
    expect(grid.get_by_role("row", name="Widget 150")).to_be_visible()
    expect(grid.get_by_role("row", name="Gadget 100")).to_be_visible()
    expect(grid.get_by_role("row", name="Gizmo 210")).to_be_visible()
    # And the totals row carries the grand total
    expect(page.get_by_test_id("report-totals")).to_contain_text("460")


def test_time_bucketed_crosstab_renders(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: a time-bucketed crosstab renders rows x month columns."""
    # Given a report of revenue per product and month
    _login(page, olap_reporting_base_url)

    # When the report page is opened
    page.goto(f"{olap_reporting_base_url}/admin/reports/olap-by-month/")

    # Then months with orders are column headers
    grid = page.get_by_test_id("report-grid")
    expect(grid.get_by_role("columnheader", name="2025-01")).to_be_visible()
    expect(grid.get_by_role("columnheader", name="2025-02")).to_be_visible()
    # And a bucket without orders for a product reads as "no data", not zero
    widget_row = grid.get_by_role("row", name="Widget")
    expect(widget_row.get_by_text("no data").first).to_be_attached()


def test_auto_bucketing_picks_quarter(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: auto bucketing picks quarter for a year-long range."""
    # Given a report whose time bucket is "auto" over orders spanning 2025
    _login(page, olap_reporting_base_url)

    # When the report page is opened
    page.goto(f"{olap_reporting_base_url}/admin/reports/olap-auto/")

    # Then the note names the chosen bucket
    expect(page.get_by_test_id("report-period-note")).to_contain_text("Auto: quarter")
    # And columns are quarters
    grid = page.get_by_test_id("report-grid")
    expect(grid.get_by_role("columnheader", name="Q1 2025")).to_be_visible()

    # When the user switches to "Month"
    page.get_by_test_id("report-period").get_by_role("link", name="Month").click()

    # Then the grid is regrouped by month and the auto note is gone
    expect(grid.get_by_role("columnheader", name="2025-01")).to_be_visible()
    expect(page.get_by_test_id("report-period-note")).to_have_count(0)


def test_csv_export_streams_dataset(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: CSV export streams the same dataset as the grid."""
    # Given the revenue-by-product report is open
    _login(page, olap_reporting_base_url)
    page.goto(f"{olap_reporting_base_url}/admin/reports/olap-by-product/")

    # When CSV is chosen from the export menu
    content = _download_text(page, olap_reporting_base_url, "olap-by-product", "csv")

    # Then the file holds each product with the same totals as the grid
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    flat = {cell for row in rows for cell in row}
    assert {"Widget", "Gadget", "Gizmo", "150", "100", "210"} <= flat


def test_xlsx_export_streams_dataset(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: XLSX export streams the same dataset as the grid."""
    # Given the revenue-by-product report is open
    _login(page, olap_reporting_base_url)
    page.goto(f"{olap_reporting_base_url}/admin/reports/olap-by-product/")

    # When Excel is chosen from the export menu
    content = _download_text(page, olap_reporting_base_url, "olap-by-product", "xlsx")

    # Then the file is a workbook (zip container) that lists the products
    assert content[:2] == b"PK"
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(content))
    values = {
        cell.value for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row
    }
    assert {"Widget", "Gadget", "Gizmo"} <= values


def test_permission_gates_report_access(page: Page, olap_reporting_base_url: str) -> None:
    """Scenario: the report permission codename gates access."""
    # Given bob, who lacks view_report_olap_by_product, is signed in
    _login(page, olap_reporting_base_url, "bob")

    # When he looks at the sidebar
    # Then the report entry is not rendered
    expect(page.get_by_test_id("sidebar")).to_be_visible()
    expect(page.get_by_test_id("nav-report-olap-by-product")).to_have_count(0)

    # And opening the report directly shows the 403 card naming the permission
    response = page.goto(f"{olap_reporting_base_url}/admin/reports/olap-by-product/")
    assert response is not None
    assert response.status == 403
    expect(page.get_by_test_id("report-forbidden")).to_be_visible()
    expect(page.get_by_test_id("report-forbidden-codename")).to_have_text(
        "view_report_olap_by_product"
    )

    # And the export is refused as well
    export = page.request.get(f"{olap_reporting_base_url}/admin/reports/olap-by-product/export.csv")
    assert export.status == 403
