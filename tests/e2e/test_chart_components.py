"""E2E: the chart fragment route and the chart frame on report pages (st-v054-charts-03).

Runs against :mod:`tests.e2e.apps.report_charts`: reports over a small orders table, one per
chart kind, plus a host page that lazy-loads a fragment. The charts are server-rendered SVG,
so there is no canvas and no Chart.js. Uses accessibility-first selectors per CLAUDE.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import expect

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _chart_titled(page: Page, name: str):
    """The chart frame whose level-3 heading is ``name`` (the page's h1 repeats the title)."""
    return page.get_by_test_id("chart-frame").filter(
        has=page.get_by_role("heading", name=name, level=3)
    )


def test_svg_line_chart_renders_from_report(page: Page, report_charts_base_url: str) -> None:
    """Scenario: a time-bucketed report draws one line per row group."""
    # Given a report of revenue per SKU and month
    # When the report page is opened
    page.goto(f"{report_charts_base_url}/admin/reports/chart-revenue-trend/")

    # Then the chart frame is lazy-loaded above the grid with an SVG labelled by the title
    frame = _chart_titled(page, "Revenue trend")
    expect(frame).to_be_visible()
    svg = frame.get_by_test_id("chart-chart-revenue-trend")
    expect(svg).to_be_visible()
    expect(svg).to_have_accessible_name("Revenue trend")
    # And there is one focusable point per month, reading out every SKU's value
    expect(
        svg.get_by_role("img", name="2025-01: beans 100, filter —, rooibos —, sencha 30")
    ).to_have_count(1)
    expect(svg.get_by_role("img")).to_have_count(4)
    # And the legend names the series
    expect(frame.get_by_role("list", name="Legend").get_by_role("listitem")).to_have_count(4)
    # And the page's own grid is still there
    expect(page.get_by_test_id("report-grid")).to_be_visible()


def test_svg_bar_chart_renders_from_report(page: Page, report_charts_base_url: str) -> None:
    """Scenario: a single-group report draws one bar per group."""
    # Given a report of revenue per category
    # When the report page is opened
    page.goto(f"{report_charts_base_url}/admin/reports/chart-by-category/")

    # Then each category is a focusable bar carrying its value
    svg = page.get_by_test_id("chart-chart-by-category")
    expect(svg).to_be_visible()
    expect(svg.get_by_role("img")).to_have_count(2)
    expect(svg.get_by_role("img", name="coffee: 200")).to_be_visible()
    expect(svg.get_by_role("img", name="tea: 100")).to_be_visible()


def test_stacked_bar_renders_one_stack_per_column(page: Page, report_charts_base_url: str) -> None:
    """Scenario: rows x columns of groups draw one stack per row, one segment per column."""
    # Given a report of revenue per category and channel
    # When the report page is opened
    page.goto(f"{report_charts_base_url}/admin/reports/chart-channel-mix/")

    # Then each category is a stack that reads out its channels
    frame = _chart_titled(page, "Channel mix")
    svg = frame.get_by_test_id("chart-chart-channel-mix")
    expect(svg).to_be_visible()
    expect(svg.get_by_role("img", name="coffee: store 40, web 160")).to_be_visible()
    expect(svg.get_by_role("img", name="tea: store 70, web 30")).to_be_visible()
    # And the legend carries one entry per channel
    legend = frame.get_by_role("list", name="Legend")
    expect(legend.get_by_role("listitem")).to_have_text(["store", "web"])


def test_chart_fragment_lazy_loads_via_htmx_in_a_host_template(
    page: Page, report_charts_base_url: str
) -> None:
    """Scenario: a host page embeds the fragment and its period switch swaps in place."""
    # Given a host page whose slot requests the chart fragment on load
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url) if "/chart" in r.url else None)

    # When the host page is opened
    page.goto(f"{report_charts_base_url}/host")

    # Then the fragment replaces the slot with the chart frame
    frame = _chart_titled(page, "Revenue trend")
    expect(frame).to_be_visible()
    expect(page.get_by_text("Loading chart…")).to_have_count(0)
    # And the period switch marks the declared period
    switch = frame.get_by_role("group", name="Period")
    expect(switch.get_by_role("button", name="Month")).to_have_attribute("aria-pressed", "true")

    # When another period is chosen
    switch.get_by_role("button", name="Quarter").click()

    # Then the frame is swapped in place, without a page navigation
    expect(frame.get_by_role("button", name="Quarter")).to_have_attribute("aria-pressed", "true")
    expect(page).to_have_url(f"{report_charts_base_url}/host")
    assert any(url.endswith("/chart?period=quarter") for url in requests)
    frame.get_by_text("Show as table").click()
    rows = frame.get_by_test_id("chart-data-table-chart-revenue-trend").get_by_role("row")
    expect(rows).to_have_count(3)  # header, 2025-Q1, 2025-Q2


def test_svg_chart_includes_accessible_data_table(page: Page, report_charts_base_url: str) -> None:
    """Scenario: every chart has its numbers as a table behind "Show as table"."""
    # Given a loaded chart of revenue per category
    page.goto(f"{report_charts_base_url}/admin/reports/chart-by-category/")
    frame = _chart_titled(page, "Revenue by category")
    expect(frame).to_be_visible()

    # When the table fallback is opened
    frame.get_by_text("Show as table").click()

    # Then it is a real table with column and row headers
    table = frame.get_by_test_id("chart-data-table-chart-by-category").get_by_role("table")
    expect(table).to_be_visible()
    expect(table.get_by_role("columnheader")).to_have_text(["Category", "Sum of Amount"])
    expect(table.get_by_role("rowheader")).to_have_text(["coffee", "tea"])
    expect(table.get_by_role("cell")).to_have_text(["200", "100"])


def test_chart_respects_the_report_filter_context(page: Page, report_charts_base_url: str) -> None:
    """Scenario: the page's query string reaches the fragment, so chart and grid agree."""
    # Given a report page opened with a period override
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url) if "/chart" in r.url else None)

    # When it is opened grouped by year
    page.goto(f"{report_charts_base_url}/admin/reports/chart-revenue-trend/?period=year")

    # Then the grid and the chart both use the year bucket
    expect(page.get_by_role("columnheader", name="2025")).to_be_visible()
    frame = _chart_titled(page, "Revenue trend")
    expect(frame).to_be_visible()
    frame.get_by_text("Show as table").click()
    table = frame.get_by_test_id("chart-data-table-chart-revenue-trend").get_by_role("table")
    expect(table.get_by_role("rowheader")).to_have_text(["2025"])
    # And the fragment was requested with the page's query string, unchanged
    assert any("period=year" in url and "embed=1" in url for url in requests)
    # And the page's "Group by" control, not a second switch, drives the period
    expect(frame.get_by_role("group", name="Period")).to_have_count(0)

    # When the page's bucket switch changes the period
    page.get_by_test_id("report-period").get_by_role("link", name="Quarter").click()

    # Then the chart follows
    frame = _chart_titled(page, "Revenue trend")
    frame.get_by_text("Show as table").click()
    table = frame.get_by_test_id("chart-data-table-chart-revenue-trend").get_by_role("table")
    expect(table.get_by_role("rowheader")).to_have_text(["2025-Q1", "2025-Q2"])


def test_chart_shows_the_no_data_state(page: Page, report_charts_base_url: str) -> None:
    """Scenario: a report without rows has no chart on its page and an empty fragment."""
    # Given a report over an empty table
    # When its page is opened
    page.goto(f"{report_charts_base_url}/admin/reports/chart-empty/")

    # Then the grid says there is no data and no chart is requested
    expect(page.get_by_test_id("report-no-data")).to_be_visible()
    expect(page.get_by_test_id("report-chart")).to_have_count(0)
    expect(page.get_by_test_id("chart-frame")).to_have_count(0)

    # When the fragment is requested directly
    page.goto(f"{report_charts_base_url}/admin/reports/chart-empty/chart")

    # Then the frame explains that there is nothing to draw
    expect(page.get_by_test_id("chart-empty")).to_contain_text("No data for this period.")


def test_chart_shows_an_error_state_when_it_cannot_be_drawn(
    page: Page, report_charts_base_url: str
) -> None:
    """Scenario: the grid still renders when the chart has a reason not to."""
    # Given a report whose sums are negative, which a stacked bar cannot draw
    # When its page is opened
    page.goto(f"{report_charts_base_url}/admin/reports/chart-balance/")

    # Then the chart frame says why, in place
    frame = _chart_titled(page, "Balance")
    expect(frame.get_by_role("alert")).to_contain_text("Stacked bars cannot show negative values.")
    # And the grid is unaffected
    expect(page.get_by_test_id("report-grid")).to_be_visible()


def test_chart_shows_an_error_state_with_retry_when_the_query_fails(
    page: Page, report_charts_base_url: str
) -> None:
    """Scenario: a failing query shows the error state with a Retry button."""
    # Given a report whose table does not exist
    # When the chart fragment is requested
    response = page.goto(f"{report_charts_base_url}/admin/reports/chart-broken/chart")

    # Then the fragment answers 200 (HTMX only swaps successful responses) with the error state
    assert response is not None
    assert response.status == 200
    expect(page.get_by_role("alert")).to_contain_text("The report query failed.")
    expect(page.get_by_role("button", name="Retry")).to_be_visible()
