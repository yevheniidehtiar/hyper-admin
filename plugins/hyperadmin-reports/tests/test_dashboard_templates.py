"""Route-level tests of the dashboard card templates and states (#463).

The first seven tests map 1:1 to the scenarios of
``.meta/epics/epicdashboard-dashboard-builder-with-widgets/stories/featui-create-dashboard-template-with-widget-cards.md``.
They assert the HTML a mounted admin serves.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from dashboard_support import (
    DashOrder,
    Mounted,
    OrderRevenueReport,
    OrdersByMonthReport,
    PayrollTotalReport,
    TextWidget,
    clean_registry,
    make_engine,
    mount,
)

from hyperadmin.core.registry import site
from hyperadmin_reports import (
    ChartWidget,
    QuickAction,
    QuickActionsWidget,
    StatWidget,
    register_widget,
)

STAT_URL = "/admin/dashboard/widgets/stat-orders-revenue"


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    yield from clean_registry()


def _widgets() -> None:
    """A stat, a chart and quick actions, in that order."""
    site.register(DashOrder)
    register_widget(StatWidget(OrderRevenueReport))
    register_widget(ChartWidget(OrdersByMonthReport))
    register_widget(
        QuickActionsWidget(
            [
                QuickAction("New order", "dashorder-create-form", permission="add_dashorder"),
                QuickAction("All reports", "reports-index", icon="file-text"),
            ]
        )
    )


def _cards(html: str) -> dict[str, str]:
    """Each card's HTML by widget key, in page order."""
    cards = {}
    for chunk in html.split("<article ")[1:]:
        card = chunk.split("</article>", 1)[0]
        match = re.search(r'data-widget-key="([^"]+)"', card)
        assert match is not None
        cards[match.group(1)] = card
    return cards


def _page(mounted: Mounted, user: str = "alice") -> str:
    response = mounted.client.get("/admin/", headers={"x-user": user})
    assert response.status_code == 200
    return response.text


def test_the_grid_renders_one_card_per_visible_widget_in_layout_order(tmp_path: Path) -> None:
    """
    Scenario: the grid renders one card per visible widget in layout order
      Given alice sees widgets [stat-orders-revenue, chart-orders-by-month, quick-actions]
      When  the dashboard page renders
      Then  data-testid="dashboard-grid" holds cards widget-stat-orders-revenue,
            widget-chart-orders-by-month, widget-quick-actions in that order
    """
    _widgets()
    mounted = mount(make_engine(tmp_path))

    html = _page(mounted)
    cards = _cards(html.split('data-testid="dashboard-grid"', 1)[1])

    assert list(cards) == ["stat-orders-revenue", "chart-orders-by-month", "quick-actions"]
    for key, card in cards.items():
        assert f'data-testid="widget-{key}"' in card
    assert 'data-span="1"' in cards["stat-orders-revenue"]
    assert 'data-span="2"' in cards["chart-orders-by-month"]
    assert '<h2 class="ha-h4" id="widget-quick-actions-title">Quick actions</h2>' in html
    # The chart card loads the report's own chart fragment into a body tests can find.
    chart = cards["chart-orders-by-month"]
    assert 'data-testid="report-chart"' in chart
    assert 'hx-get="/admin/reports/orders-by-month/chart?embed=1"' in chart
    assert 'href="/admin/reports/orders-by-month/"' in chart
    # Quick actions are rendered with the page: no request, and only what alice may use.
    actions = cards["quick-actions"]
    assert "hx-get" not in actions.split("data-widget-body", 1)[1]
    assert '<a href="/admin/dashorder/create" class="ha-btn ha-btn-secondary">' in actions
    assert 'href="/admin/reports/"' in actions
    assert "/static/plugins/reports/charts.css" in html
    assert mounted.client.get("/admin/static/plugins/reports/dashboard.css").status_code == 200


def test_a_stat_card_shows_the_value_and_links_to_its_report(tmp_path: Path) -> None:
    """
    Scenario: a stat card shows the value and links to its report
      Given the "orders-revenue" total is 600
      When  the stat widget body renders
      Then  data-testid="stat-stat-orders-revenue" shows "600"
      And   the card has an "Open report" link to {prefix}/reports/orders-revenue/
    """
    _widgets()
    mounted = mount(make_engine(tmp_path))

    body = mounted.client.get(STAT_URL)
    card = _cards(_page(mounted))["stat-orders-revenue"]

    assert body.status_code == 200
    assert '<span class="ha-stat__value" data-testid="stat-stat-orders-revenue">600</span>' in (
        body.text
    )
    assert "Orders revenue" in body.text
    assert "<html" not in body.text
    link = next(tag for tag in card.split("<a ") if 'data-testid="widget-open"' in tag)
    assert link.startswith('href="/admin/reports/orders-revenue/"')
    assert "Open report" in link


def test_a_stat_card_without_data_shows_an_em_dash(tmp_path: Path) -> None:
    """
    Scenario: a stat card without data shows an em dash
      Given the "orders-revenue" total is None
      When  the stat widget body renders
      Then  the value shows "—"
      And   a muted line says "No data"
    """
    _widgets()
    mounted = mount(make_engine(tmp_path, amounts=()))

    body = mounted.client.get(STAT_URL).text

    assert 'data-testid="stat-stat-orders-revenue">&mdash;</span>' in body
    assert '<span class="ha-caption ha-muted">No data</span>' in body


def test_a_lazy_card_shows_a_skeleton_and_a_fallback_link_before_it_loads(tmp_path: Path) -> None:
    """
    Scenario: a lazy card shows a skeleton and a fallback link before it loads
      Given a StatWidget card
      When  the page HTML is served
      Then  the card body has hx-get to its fragment URL, hx-trigger="load" and aria-busy="true"
      And   the body contains an "Open report" link
    """
    _widgets()
    mounted = mount(make_engine(tmp_path))

    card = _cards(_page(mounted))["stat-orders-revenue"]
    body = card.split("data-widget-body", 1)[1]

    assert f'hx-get="{STAT_URL}"' in body
    assert 'hx-trigger="load"' in body
    assert 'aria-busy="true"' in body
    assert 'class="ha-skel' in body
    assert "Loading Sum of Amount" in body
    assert "stat-stat-orders-revenue" not in card  # the number arrives with the fragment
    assert "Open report" in card
    assert 'href="/admin/reports/orders-revenue/"' in card


def test_a_failed_widget_shows_an_error_state_with_retry(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: a failed widget shows an error state with Retry
      Given the service returned the error body for widget "broken"
      When  the body renders
      Then  it shows data-testid="widget-error" with the text "Widget unavailable"
      And   a Retry button re-requests the widget fragment
    """
    _widgets()
    register_widget(TextWidget("broken", fail=True))
    register_widget(TextWidget("inline-broken", fail=True, lazy=False))
    mounted = mount(make_engine(tmp_path))

    with caplog.at_level(logging.ERROR, logger="hyperadmin_reports.dashboard.service"):
        body = mounted.client.get("/admin/dashboard/widgets/broken")
        page = _page(mounted)

    assert body.status_code == 200
    assert 'data-testid="widget-error"' in body.text
    assert "Widget unavailable" in body.text
    retry = next(tag for tag in body.text.split("<button ") if 'data-testid="widget-retry"' in tag)
    assert 'hx-get="/admin/dashboard/widgets/broken"' in retry
    assert 'hx-target="closest [data-widget-body]"' in retry
    assert "Retry" in retry
    # A widget rendered with the page fails in place; the stat card still gets its fragment.
    cards = _cards(page)
    assert 'data-testid="widget-error"' in cards["inline-broken"]
    assert 'hx-get="/admin/dashboard/widgets/inline-broken"' in cards["inline-broken"]
    assert f'hx-get="{STAT_URL}"' in cards["stat-orders-revenue"]
    assert mounted.client.get(STAT_URL).status_code == 200
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert {r.getMessage() for r in errors} == {
        "dashboard widget 'broken' failed to render",
        "dashboard widget 'inline-broken' failed to render",
    }
    assert all(r.exc_info for r in errors)


def test_a_user_without_visible_widgets_sees_the_empty_state(tmp_path: Path) -> None:
    """
    Scenario: a user without visible widgets sees the empty state
      Given the user may view none of the registered widgets
      When  the dashboard page renders
      Then  it shows data-testid="dashboard-empty"
      And   no "Reset layout" button is shown
    """
    register_widget(StatWidget(OrderRevenueReport))
    register_widget(StatWidget(PayrollTotalReport))
    mounted = mount(make_engine(tmp_path))

    html = _page(mounted, user="nobody")

    assert 'data-testid="dashboard-empty"' in html
    assert 'data-testid="dashboard-grid"' not in html
    assert 'data-testid="dashboard-reset"' not in html
    assert "Reset layout" not in html
    assert _cards(html) == {}
    assert "Welcome to HyperAdmin Dashboard" not in html


def test_reorder_controls_are_hidden_without_persistence(tmp_path: Path) -> None:
    """
    Scenario: reorder controls are hidden without persistence
      Given the service cannot persist for the request
      When  the dashboard page renders
      Then  no card has widget-move-up, widget-move-down or widget-drag-handle
      And   no dashboard-reset button is shown
    """
    _widgets()
    controls = ("widget-move-up", "widget-move-down", "widget-drag-handle", "dashboard-reset")
    signed_in = mount(make_engine(tmp_path))
    (tmp_path / "anonymous").mkdir()
    anonymous = mount(make_engine(tmp_path / "anonymous"), auth=False)

    with_controls = _page(signed_in)
    without_controls = _page(anonymous)

    for testid in controls:
        assert f'data-testid="{testid}"' in with_controls
        assert f'data-testid="{testid}"' not in without_controls
    assert "data-dashboard-live" in with_controls
    assert "data-dashboard-live" not in without_controls
    assert list(_cards(without_controls)) == list(_cards(with_controls))
    # The first card cannot move up and the last cannot move down, but both keep the focus.
    cards = _cards(with_controls)
    first_up = cards["stat-orders-revenue"].split('value="up"', 1)[1].split(">", 1)[0]
    last_down = cards["quick-actions"].split('value="down"', 1)[1].split(">", 1)[0]
    middle = cards["chart-orders-by-month"]
    assert 'aria-disabled="true"' in first_up
    assert 'aria-disabled="true"' in last_down
    assert "aria-disabled" not in middle
    assert " disabled" not in first_up
    assert 'aria-label="Move Orders by month up"' in middle
    assert 'aria-label="Drag to reorder Orders by month"' in middle
    assert 'name="csrf_token"' in middle


def test_quick_actions_without_usable_actions_say_so(tmp_path: Path) -> None:
    """
    Scenario: a quick actions card with nothing the user may use says so
      Given a QuickActionsWidget whose only action needs add_dashorder
      And   user "viewer" lacks it
      When  viewer opens the dashboard
      Then  the card says "No actions available."
    """
    site.register(DashOrder)
    register_widget(
        QuickActionsWidget(
            [QuickAction("New order", "dashorder-create-form", permission="add_dashorder")]
        )
    )
    mounted = mount(make_engine(tmp_path))

    card = _cards(_page(mounted, user="viewer"))["quick-actions"]

    assert 'data-testid="widget-actions-empty"' in card
    assert "No actions available." in card
    assert "New order" not in card


def test_the_chart_widget_fragment_is_the_placeholder_of_the_report_chart(tmp_path: Path) -> None:
    """
    Scenario: the dashboard's own fragment of a chart widget points at the report chart
      Given a ChartWidget over "orders-by-month"
      When  GET {prefix}/dashboard/widgets/chart-orders-by-month
      Then  the response is the loading placeholder requesting the report chart fragment
      And   that fragment is the report's chart frame
    """
    _widgets()
    mounted = mount(make_engine(tmp_path))

    placeholder = mounted.client.get("/admin/dashboard/widgets/chart-orders-by-month")
    chart = mounted.client.get("/admin/reports/orders-by-month/chart?embed=1")

    assert placeholder.status_code == 200
    assert 'hx-get="/admin/reports/orders-by-month/chart?embed=1"' in placeholder.text
    assert 'hx-swap="outerHTML"' in placeholder.text
    assert 'data-testid="chart-frame"' in chart.text
