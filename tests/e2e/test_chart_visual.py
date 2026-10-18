"""Visual baseline and keyboard behaviour of the SVG chart components.

The ``hyperadmin-reports`` chart macros are rendered into a standalone demo page that links
the shipped core ``hyperadmin.css`` and the plugin's ``charts.css``, so the snapshot pins the
real component CSS without needing a report route (that lands with the chart fragment
route). Until the plugin registry wires plugin templates into the admin, the demo renders
through a test-local loader. Baselines live next to the responsive ones and refresh the
same way (``RESPONSIVE_SNAPSHOTS_UPDATE=1``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from jinja2 import ChoiceLoader, FileSystemLoader

import hyperadmin_reports
from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin_reports.charts import (
    BarChart,
    LineChart,
    PeriodOption,
    Series,
    Sparkline,
    StackedBarChart,
)
from tests.e2e.test_visual_regression import VIEWPORTS, _capture_or_compare

if TYPE_CHECKING:
    from playwright.sync_api import Page

CSS = (
    Path(__file__).resolve().parents[2] / "src" / "hyperadmin" / "static" / "css" / "hyperadmin.css"
)
PLUGIN = Path(hyperadmin_reports.__file__).parent
CHART_CSS = PLUGIN / "static" / "hyperadmin_reports" / "charts.css"

MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]

DEMO = """
{%- from "hyperadmin_reports/charts/frame.html" import chart_frame -%}
{%- from "hyperadmin_reports/charts/sparkline.html" import sparkline -%}
<!doctype html>
<html lang="en" data-theme="light">
<head><meta charset="utf-8"><title>Charts</title><link rel="stylesheet" href="{{ css }}"><link rel="stylesheet" href="{{ chart_css }}"></head>
<body><main style="padding:16px;max-width:960px">
{{ chart_frame(line, caption="Last 12 months · EUR", periods=periods) }}
<div class="ha-grid">
{{ chart_frame(bar, caption="EUR thousands") }}
{{ chart_frame(stacked, caption="EUR thousands") }}
</div>
<div class="ha-grid">
{{ chart_frame(bar, state="loading") }}
{{ chart_frame(empty, message="No invoices in this period.") }}
{{ chart_frame(bar, state="error", message="The report query timed out.", retry_url="#") }}
</div>
<div class="ha-card" style="max-width:240px">{{ sparkline(spark) }}</div>
</main></body></html>
"""


def _k(value: float) -> str:
    return f"€{value:g}k"


@pytest.fixture
def chart_page(page: Page, tmp_path: Path) -> Page:
    admin = Admin(app=MagicMock(spec=FastAPI), settings=HyperAdminSettings(create_tables=False))
    core = admin.templates.env
    env = core.overlay(loader=ChoiceLoader([FileSystemLoader(PLUGIN / "templates"), core.loader]))
    html = env.from_string(DEMO).render(
        css=CSS.as_uri(),
        chart_css=CHART_CSS.as_uri(),
        line=LineChart(
            "revenue",
            title="Revenue and costs",
            desc="Revenue grew from €42k to €71k; costs rose more slowly.",
            labels=MONTHS,
            x_title="Month",
            series=[
                Series("Revenue", [42, 45, 44, 51, 49, 55, 58, 54, 61, 66, 63, 71]),
                Series("Costs", [30, 31, 33, 32, 35, 36, 38, 37, 39, 41, 42, 44]),
            ],
            format_value=_k,
            format_tick=_k,
        ),
        periods=[
            PeriodOption("3M", "#3m"),
            PeriodOption("6M", "#6m"),
            PeriodOption("12M", "#12m", active=True),
        ],
        bar=BarChart(
            "quarters",
            title="Revenue per quarter",
            labels=["Q1", "Q2", "Q3", "Q4"],
            series=[Series("Revenue", [120, 140, 155, 170])],
            width=380,
            height=200,
        ),
        stacked=StackedBarChart(
            "streams",
            title="Revenue by stream",
            labels=["Q1", "Q2", "Q3", "Q4"],
            series=[
                Series("Services", [120, 140, 155, 170]),
                Series("Licences", [40, 55, 50, 70]),
                Series("Other", [20, 25, 35, 30]),
            ],
            width=380,
            height=200,
        ),
        empty=LineChart("empty", title="Invoices", labels=["Oct"], series=[Series("n", [None])]),
        spark=Sparkline([36, 33, 34, 26, 28, 22, 18, 23, 15, 10, 13, 4]),
    )
    demo = tmp_path / "charts.html"
    demo.write_text(html, encoding="utf-8")
    page.goto(demo.as_uri())
    page.wait_for_load_state("networkidle")
    return page


def test_chart_components_baseline(chart_page: Page) -> None:
    """
    Scenario: chart components match the committed visual baseline.

      Given the line, bar and stacked-bar frames plus the loading, no-data and error states
      When  the demo page renders at 1024px
      Then  the screenshot matches the committed baseline
    """
    chart_page.set_viewport_size(VIEWPORTS["1024px"])
    _capture_or_compare(chart_page, "charts", "1024px")


def test_tooltip_shows_on_keyboard_focus(chart_page: Page) -> None:
    """
    Scenario: a point's tooltip appears on keyboard focus.

      Given the revenue line chart
      When  the hit area for May receives keyboard focus
      Then  May's tooltip becomes visible and the other tooltips stay hidden
    """
    # Given
    may = chart_page.get_by_role("img", name="May: Revenue €58k, Costs €38k")
    oct_ = chart_page.get_by_role("img", name="Oct: Revenue €71k, Costs €44k")
    tip_opacity = "el => getComputedStyle(el.parentElement.lastElementChild).opacity"
    # When
    may.focus()
    # Then
    assert may.evaluate(tip_opacity) == "1"
    assert oct_.evaluate(tip_opacity) == "0"


def test_table_fallback_opens(chart_page: Page) -> None:
    """
    Scenario: the data table fallback opens from its summary.

      Given the revenue chart frame
      When  the user opens "Show as table"
      Then  the twelve monthly rows are visible
    """
    # Given
    table = chart_page.get_by_test_id("chart-data-table-revenue")
    # When
    table.get_by_text("Show as table").click()
    # Then
    assert table.get_by_role("row").count() == 13
    assert table.get_by_role("rowheader", name="Oct").is_visible()
