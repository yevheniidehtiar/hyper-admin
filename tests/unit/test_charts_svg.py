"""Geometry and markup tests for the server-rendered SVG charts.

Scenarios adapted from
``.meta/epics/epic-v054-chart-components/stories/featwidgets-svg-chart-primitives.md``
and the design-system contract in ``docs/design/system/components/Chart/README.md``.
Templates render through a real ``Admin`` Jinja environment (i18n wired), so these are
also the integration tests for the public ``hyperadmin.widgets`` surface.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from hyperadmin.core.app import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.widgets import (
    BarChart,
    LineChart,
    PeriodOption,
    Series,
    Sparkline,
    StackedBarChart,
)

MONTHS = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
REVENUE = [42, 45, 44, 51, 49, 55, 58, 54, 61, 66, 63, 71]
COSTS = [30, 31, 33, 32, 35, 36, 38, 37, 39, 41, 42, 44]


@pytest.fixture(scope="module")
def env():
    admin = Admin(app=MagicMock(spec=FastAPI), settings=HyperAdminSettings(create_tables=False))
    return admin.templates.env


def render(env, template: str, macro: str, *args, **kwargs) -> str:
    source = f'{{% from "components/charts/{template}" import {macro} %}}{{{{ {macro}(*a, **k) }}}}'
    return env.from_string(source).render(a=args, k=kwargs)


def svg_of(markup: str) -> ET.Element:
    """Parse the first <svg> in ``markup`` as XML, which also proves it is well-formed."""
    match = re.search(r"<svg class=\"ha-chart[^\"]*\".*?</svg>", markup, re.DOTALL)
    assert match, markup
    return ET.fromstring(match.group(0))  # noqa: S314 - markup rendered by this test


def revenue_chart(**kwargs) -> LineChart:
    return LineChart(
        "revenue",
        title="Revenue and costs, last 12 months",
        labels=MONTHS,
        series=[Series("Revenue", REVENUE), Series("Costs", COSTS)],
        x_title="Month",
        **kwargs,
    )


def quarter_bars(values=(120, 140, 155, 170), **kwargs) -> BarChart:
    return BarChart(
        "quarters",
        title="Revenue per quarter",
        labels=["Q1", "Q2", "Q3", "Q4"][: len(values)],
        series=[Series("Revenue", values)],
        width=380,
        height=200,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["", "has space", "-lead", "a/b"])
def test_key_must_be_a_safe_identifier(key: str) -> None:
    """The key becomes an id and a data-testid, so it cannot contain spaces or slashes."""
    with pytest.raises(ValueError, match="chart key"):
        LineChart(key, title="t", labels=["a"], series=[Series("s", [1])])
    with pytest.raises(ValueError, match="chart key"):
        Sparkline([1], key=key or "-")


@pytest.mark.parametrize("count", [0, 7])
def test_series_count_is_bounded_by_the_palette(count: int) -> None:
    """Six categorical slots exist (ha-chart-1 … 6); more would reuse a colour."""
    with pytest.raises(ValueError, match="1 to 6 series"):
        LineChart("k", title="t", labels=["a"], series=[Series(str(i), [1]) for i in range(count)])


def test_series_length_must_match_labels() -> None:
    with pytest.raises(ValueError, match="2 values for 3 labels"):
        LineChart("k", title="t", labels=["a", "b", "c"], series=[Series("s", [1, 2])])


def test_bar_chart_takes_exactly_one_series() -> None:
    with pytest.raises(ValueError, match="exactly one series"):
        BarChart("k", title="t", labels=["a"], series=[Series("x", [1]), Series("y", [2])])


def test_stacked_bar_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="zero or positive"):
        StackedBarChart("k", title="t", labels=["a"], series=[Series("x", [-1])])


def test_series_values_are_frozen_to_a_tuple() -> None:
    assert Series("s", [1, 2]).values == (1, 2)


# ---------------------------------------------------------------------------
# Line chart geometry (matches the design-system preview)
# ---------------------------------------------------------------------------


def test_line_chart_geometry_matches_the_design_system_preview() -> None:
    """
    Scenario: the revenue line chart reproduces the design-system preview.

      Given twelve months of revenue and costs at the 800x240 design width
      When  the geometry is computed
      Then  ticks run €0k–€80k at 50px steps, every second month is labelled
      And   the revenue path starts at (44, 107) like the preview
    """
    chart = revenue_chart()
    assert [(t.y, t.label, t.text_y) for t in chart.y_ticks][:2] == [
        (212.0, "0", 216.0),
        (162.0, "20", 166.0),
    ]
    assert [lbl.text for lbl in chart.x_labels] == ["Dec", "Feb", "Apr", "Jun", "Aug", "Oct"]
    assert chart.paths[0].d.startswith("M44.0 107.0 L111.3 99.5")
    assert chart.paths[0].dashed is False
    assert chart.paths[1].dashed is True
    assert chart.zero_y == 212.0
    assert chart.tick_x == 36.0


def test_line_end_labels_sit_above_the_line_end() -> None:
    chart = revenue_chart()
    assert [(m.text, m.x, m.y, m.cls) for m in chart.end_labels] == [
        ("Revenue", 780.0, 24.5, "s1"),
        ("Costs", 780.0, 92.0, "s2"),
    ]


def test_colliding_end_label_moves_below_the_line() -> None:
    chart = LineChart(
        "k",
        title="t",
        labels=["a", "b"],
        series=[Series("A", [1, 50]), Series("B", [1, 49])],
    )
    first, second = chart.end_labels
    assert second.y - first.y >= 14


def test_end_labels_give_way_to_the_legend_with_three_series() -> None:
    chart = LineChart(
        "k", title="t", labels=["a"], series=[Series(n, [1]) for n in ("A", "B", "C")]
    )
    assert chart.end_labels == []


def test_series_ending_in_a_gap_gets_no_end_label() -> None:
    chart = LineChart("k", title="t", labels=["a", "b"], series=[Series("A", [1, None])])
    assert chart.end_labels == []


def test_missing_values_break_the_line_and_all_missing_series_draw_nothing() -> None:
    chart = LineChart(
        "k",
        title="t",
        labels=["a", "b", "c", "d"],
        series=[Series("A", [1, None, 3, 4]), Series("B", [None] * 4)],
    )
    (path,) = chart.paths
    assert path.d.count("M") == 2
    assert len(chart.hovers) == 3  # the all-missing x position has no hit area


def test_single_point_line_sits_in_the_middle() -> None:
    chart = LineChart("k", title="t", labels=["Only"], series=[Series("A", [5])])
    assert chart.xs == [chart.left + chart.plot_width / 2]
    assert chart.x_labels[0].text == "Only"


def test_tooltip_opens_to_the_right_and_flips_left_at_the_end() -> None:
    """
    Scenario: tooltips stay inside the plot.

      Given the first and the last month
      When  their tooltips are placed
      Then  the first opens to the right of its point and the last flips to the left
    """
    first, *_, last = revenue_chart().hovers
    assert first.tip.x == 54.0
    assert first.tip.rows[0] == (75.0, "Nov · Revenue ", "42")
    assert first.tip.text_x == 64.0
    assert last.tip.x + last.tip.width <= 784.0
    assert first.label == "Nov: Revenue 42, Costs 30"
    assert first.marker.cls == "s1"


def test_formatter_is_used_for_values_and_ticks() -> None:
    chart = revenue_chart(format_value=lambda v: f"€{v:g}k", format_tick=lambda v: f"€{v:g}k")
    assert chart.y_ticks[-1].label == "€80k"
    assert chart.hovers[0].label == "Nov: Revenue €42k, Costs €30k"


# ---------------------------------------------------------------------------
# Bar and stacked bar geometry
# ---------------------------------------------------------------------------


def test_bar_takes_sixty_percent_of_its_band() -> None:
    chart = quarter_bars()
    bar = chart.bars[0]
    assert bar.rect.width == pytest.approx(chart.band * 0.6, abs=0.1)
    assert bar.rect.y + bar.rect.height == chart.zero_y
    assert bar.label == "Q1: 120"
    assert bar.value_label.text == "120"
    assert bar.value_label.y == bar.rect.y - 6


def test_negative_bar_hangs_below_zero_with_label_underneath() -> None:
    chart = quarter_bars((-20, 40))
    neg = chart.bars[0]
    assert neg.rect.y == chart.zero_y
    assert neg.value_label.y > neg.rect.y + neg.rect.height


def test_missing_bar_is_skipped_and_wide_value_label_is_dropped() -> None:
    chart = BarChart(
        "k",
        title="t",
        labels=[str(i) for i in range(40)],
        series=[Series("v", [None] + [123456] * 39)],
    )
    assert len(chart.bars) == 39
    assert chart.bars[0].value_label is None  # "123,456" does not fit an 18px band


def test_stacked_segments_follow_the_cumulative_total() -> None:
    chart = StackedBarChart(
        "streams",
        title="Revenue by stream",
        labels=["Q1", "Q2"],
        series=[Series("Services", [120, None]), Series("Licences", [40, 0])],
        width=380,
        height=200,
    )
    (stack,) = chart.stacks  # Q2 has nothing to stack
    low, high = stack.segments
    assert low.y == high.y + high.height
    assert (low.cls, high.cls) == ("f1", "f2")
    assert stack.hit.label == "Q1: Services 120, Licences 40"
    assert low.x2 == round(low.x + low.width, 1)


# ---------------------------------------------------------------------------
# Sparkline geometry
# ---------------------------------------------------------------------------


def test_sparkline_scales_min_to_max_and_marks_the_last_point() -> None:
    spark = Sparkline([1, 2, None, 4])
    assert spark.d == "M2.0 36.0 L67.3 25.3 M198.0 4.0"
    assert spark.end == (198.0, 4.0)
    assert not spark.is_empty


def test_flat_and_single_value_sparklines_sit_mid_height() -> None:
    assert Sparkline([3, 3]).end == (198.0, 20.0)
    assert Sparkline([3]).end == (100.0, 20.0)


def test_empty_sparkline_has_no_end() -> None:
    spark = Sparkline([None, None])
    assert spark.is_empty
    assert spark.end is None
    assert spark.d == ""


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------


def test_line_svg_is_a_labelled_group_with_title_and_desc(env) -> None:
    """
    Scenario: the line chart is accessible.

      When  the line macro renders
      Then  the SVG is role="group" labelled by its <title> and described by its <desc>
      And   every month has a focusable hit area with all its values in aria-label
    """
    out = render(env, "line.html", "line_chart", revenue_chart(desc="Revenue grew."))
    svg = svg_of(out)
    assert svg.get("role") == "group"
    assert svg.get("aria-labelledby") == "chart-revenue-title"
    assert svg.get("aria-describedby") == "chart-revenue-desc"
    assert svg.get("data-testid") == "chart-revenue"
    assert svg.find("title").text == "Revenue and costs, last 12 months"
    assert svg.find("desc").text == "Revenue grew."
    hits = [r for r in svg.iter("rect") if r.get("class") == "pt-hit"]
    assert len(hits) == 12
    assert all(h.get("tabindex") == "0" for h in hits)
    assert 'stroke-dasharray="6 4"' in out
    assert '<tspan class="k">Nov · Revenue </tspan>42' in out


def test_svg_without_desc_has_no_describedby(env) -> None:
    svg = svg_of(render(env, "line.html", "line_chart", revenue_chart()))
    assert svg.get("aria-describedby") is None
    assert svg.find("desc") is None


def test_bar_chart_renders_one_bar_per_category(env) -> None:
    """
    Scenario: BarChart renders one bar per category.

      Given a dataset [(A, 10), (B, 20), (C, 30)]
      When  the bar macro renders
      Then  the output contains exactly three focusable bars with class f1
    """
    chart = BarChart("abc", title="ABC", labels=["A", "B", "C"], series=[Series("v", [10, 20, 30])])
    svg = svg_of(render(env, "bar.html", "bar_chart", chart))
    bars = [r for r in svg.iter("rect") if r.get("class") == "f1"]
    assert len(bars) == 3
    assert [b.get("aria-label") for b in bars] == ["A: 10", "B: 20", "C: 30"]


def test_long_category_label_is_truncated_with_ellipsis(env) -> None:
    """
    Scenario: long category label is truncated with ellipsis.

      Given a category label "supercalifragilisticexpialidocious" (>18 chars)
      When  the chart renders with default width
      Then  the rendered tspan text ends with "…" and the full label is kept in <title>
    """
    chart = BarChart(
        "long",
        title="t",
        labels=["supercalifragilisticexpialidocious", "b"],
        series=[Series("v", [1, 2])],
    )
    svg = svg_of(render(env, "bar.html", "bar_chart", chart))
    label = next(t for t in svg.iter("text") if t.find("title") is not None)
    assert label.find("tspan").text.endswith("…")
    assert label.find("title").text == "supercalifragilisticexpialidocious"


def test_stacked_bar_markup_has_separators_and_hit_areas(env) -> None:
    chart = StackedBarChart(
        "streams",
        title="t",
        labels=["Q1", "Q2"],
        series=[Series("A", [1, 2]), Series("B", [3, 4])],
    )
    svg = svg_of(render(env, "stacked_bar.html", "stacked_bar_chart", chart))
    groups = [g for g in svg.iter("g") if g.get("class") == "stack"]
    assert len(groups) == 2
    assert len([ln for ln in svg.iter("line") if ln.get("class") == "sep"]) == 4
    hit = next(r for r in svg.iter("rect") if r.get("class") == "pt-hit")
    assert hit.find("title").text == "Q1: A 1, B 3"


def test_sparkline_is_decorative_without_a_title(env) -> None:
    svg = svg_of(render(env, "sparkline.html", "sparkline", Sparkline([1, 2, 3])))
    assert svg.get("aria-hidden") == "true"
    assert svg.get("role") is None
    assert svg.find("path").get("vector-effect") == "non-scaling-stroke"


def test_sparkline_with_title_is_an_image(env) -> None:
    spark = Sparkline([1, 2, 3], key="trend", title="Revenue trend")
    svg = svg_of(render(env, "sparkline.html", "sparkline", spark))
    assert svg.get("role") == "img"
    assert svg.get("data-testid") == "chart-trend"
    assert svg.find("title").text == "Revenue trend"


def test_empty_sparkline_draws_no_path(env) -> None:
    svg = svg_of(render(env, "sparkline.html", "sparkline", Sparkline([None])))
    assert svg.find("path") is None


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------


def test_data_table_fallback_enumerates_the_source_rows(env) -> None:
    """
    Scenario: data-table fallback enumerates the source rows.

      When  the chart frame renders
      Then  it contains <details data-testid="chart-data-table-revenue"> after the SVG
      And   the table has one body row per data point
    """
    out = render(env, "frame.html", "chart_frame", revenue_chart())
    details = out.index('data-testid="chart-data-table-revenue"')
    assert out.index("<svg") < details
    body = out[details:].split("<tbody", 1)[1]
    assert body.count("<tr") == 12
    assert '<th class="ha-table-th" scope="col">Month</th>' in out
    assert "Show as table" in out


def test_frame_has_heading_caption_periods_and_dashed_legend(env) -> None:
    periods = [
        PeriodOption("6M", "/admin/reports/r/chart?period=6m"),
        PeriodOption("12M", "/admin/reports/r/chart?period=12m", active=True),
    ]
    out = render(
        env, "frame.html", "chart_frame", revenue_chart(), caption="Last 12 months", periods=periods
    )
    assert 'data-testid="chart-frame"' in out
    assert 'aria-labelledby="chart-revenue-heading"' in out
    assert "Last 12 months" in out
    assert 'aria-pressed="true" hx-get="/admin/reports/r/chart?period=12m"' in out
    assert 'href="/admin/reports/r/chart?period=6m" role="button" aria-pressed="false"' in out
    assert 'class="ha-legend__dash"' in out
    assert '<i class="k1" aria-hidden="true"></i>Revenue' in out


@pytest.mark.parametrize(
    "chart",
    [
        quarter_bars(),
        StackedBarChart("s", title="t", labels=["a"], series=[Series("x", [1]), Series("y", [2])]),
    ],
)
def test_frame_dispatches_on_chart_kind(env, chart) -> None:
    out = render(env, "frame.html", "chart_frame", chart)
    assert f'data-testid="chart-{chart.key}"' in out
    assert ('class="ha-legend"' in out) is (len(chart.series) > 1)
    assert "ha-legend__dash" not in out


def test_frame_loading_state_is_busy_and_keeps_the_chart_height(env) -> None:
    out = render(env, "frame.html", "chart_frame", revenue_chart(), state="loading")
    assert 'aria-busy="true"' in out
    assert 'class="ha-chart ha-skel" viewBox="0 0 800 240"' in out
    assert "Loading chart" in out
    assert "chart-data-table" not in out


def test_frame_no_data_state(env) -> None:
    chart = LineChart(
        "k", title="t", labels=["a"], series=[Series("A", [None]), Series("B", [None])]
    )
    out = render(env, "frame.html", "chart_frame", chart, message="No invoices in this period.")
    assert 'data-testid="chart-empty"' in out
    assert "No invoices in this period." in out
    assert '<svg class="ha-chart' not in out
    assert 'class="ha-legend"' not in out


def test_frame_error_state_with_retry(env) -> None:
    out = render(
        env,
        "frame.html",
        "chart_frame",
        revenue_chart(),
        state="error",
        message="The report query timed out.",
        retry_url="/admin/reports/r/chart",
    )
    assert 'role="alert"' in out
    assert "The report query timed out." in out
    assert 'hx-get="/admin/reports/r/chart" hx-target="closest section"' in out
    assert ">Retry</button>" in out


def test_frame_error_state_without_retry_uses_default_message(env) -> None:
    out = render(env, "frame.html", "chart_frame", revenue_chart(), state="error")
    assert "The chart could not be loaded." in out
    assert "Retry" not in out


def test_chart_text_is_autoescaped(env) -> None:
    chart = LineChart("k", title="<b>x</b>", labels=["<a>"], series=[Series("<s>", [1])])
    out = render(env, "frame.html", "chart_frame", chart)
    assert "<b>x</b>" not in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out
