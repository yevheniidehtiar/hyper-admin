"""Unit tests for the dashboard widgets and the widget registry (#457).

The first eight tests map 1:1 to the scenarios of
``.meta/epics/epicdashboard-dashboard-builder-with-widgets/stories/featdashboard-create-dashboardwidget-protocol-and-built-in-w.md``.
Widgets are exercised inside a real admin request (see ``dashboard_support.Mounted.run``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dashboard_support import (
    DashOrder,
    GrandTotalReport,
    OrderRevenueReport,
    OrdersByMonthReport,
    SkuListReport,
    TextWidget,
    clean_registry,
    make_engine,
    mount,
)
from starlette.requests import Request

from hyperadmin.core.registry import site
from hyperadmin_reports import (
    ChartWidget,
    QuickAction,
    QuickActionsWidget,
    StatWidget,
    WidgetBody,
    get_widget,
    register_report,
    register_widget,
    registered_widgets,
    unregister_report,
    unregister_widget,
)
from hyperadmin_reports.dashboard.widgets import LAZY_TEMPLATE


@pytest.fixture(autouse=True)
def _registered() -> Iterator[None]:
    yield from clean_registry()


def test_stat_widget_totals_its_report_aggregate(tmp_path: Path) -> None:
    """
    Scenario: stat widget totals its report aggregate
      Given the registered report "orders-revenue" sums Order.amount grouped by status
      And   Orders have amounts 100, 200 and 300
      When  StatWidget(OrderRevenueReport).render(request, admin) is awaited
      Then  the body context has value == 600
      And   the body links to the "orders-revenue" report page
    """
    mounted = mount(make_engine(tmp_path), auth=False)
    widget = StatWidget(OrderRevenueReport)

    async def call(request: Request) -> WidgetBody:
        return await widget.render(request, mounted.admin)

    body = mounted.run(call)

    assert body.template == "dashboard/_stat.html"
    assert body.context["value"] == 600
    assert body.context["detail_url"] == "/admin/reports/orders-revenue/"
    assert body.context["widget"] is widget
    assert (widget.key, widget.title, widget.span) == ("stat-orders-revenue", "Sum of Amount", 1)
    assert widget.permission() == "view_report_orders_revenue"
    assert widget.detail_label == "Open report"


def test_stat_widget_without_rows_has_no_value(tmp_path: Path) -> None:
    """
    Scenario: stat widget without rows has no value
      Given the registered report "orders-revenue" and no Order rows
      When  the stat widget renders
      Then  the body context has value is None
    """
    mounted = mount(make_engine(tmp_path, amounts=()), auth=False)
    widget = StatWidget(OrderRevenueReport)

    async def call(request: Request) -> WidgetBody:
        return await widget.render(request, mounted.admin)

    assert mounted.run(call).context["value"] is None


def test_chart_widget_points_at_the_report_chart_fragment(tmp_path: Path) -> None:
    """
    Scenario: chart widget points at the report chart fragment
      Given the registered chartable report "orders-by-month"
      When  ChartWidget(OrdersByMonthReport).fragment_url(request) is called
      Then  the result is {prefix}/reports/orders-by-month/chart?embed=1
      And   permission() is "view_report_orders_by_month"
    """
    mounted = mount(make_engine(tmp_path), auth=False)
    widget = ChartWidget(OrdersByMonthReport)

    async def call(request: Request) -> tuple[str, WidgetBody]:
        return widget.fragment_url(request), await widget.render(request, mounted.admin)

    url, body = mounted.run(call)

    assert url == "/admin/reports/orders-by-month/chart?embed=1"
    assert widget.permission() == "view_report_orders_by_month"
    assert (widget.key, widget.title, widget.span) == (
        "chart-orders-by-month",
        "Orders by month",
        2,
    )
    assert widget.body_testid == "report-chart"
    assert body.template == LAZY_TEMPLATE
    assert body.context["fragment_url"] == url
    assert body.context["detail_url"] == "/admin/reports/orders-by-month/"


def test_quick_actions_keep_only_the_actions_the_user_may_use(tmp_path: Path) -> None:
    """
    Scenario: quick actions keep only the actions the user may use
      Given a QuickActionsWidget with "New order" (permission add_order) and "All reports"
            (no permission)
      And   a user without add_order
      When  the widget renders for that user
      Then  the body lists "All reports"
      And   the body does not list "New order"
    """
    site.register(DashOrder)
    mounted = mount(make_engine(tmp_path))
    widget = QuickActionsWidget(
        [
            QuickAction("New order", "dashorder-create-form", permission="add_dashorder"),
            QuickAction("All reports", "reports-index", icon="file-text"),
        ]
    )

    async def call(request: Request) -> WidgetBody:
        return await widget.render(request, mounted.admin)

    viewer = mounted.run(call, user="viewer")
    alice = mounted.run(call, user="alice")

    assert viewer.template == "dashboard/_actions.html"
    assert viewer.context["actions"] == [
        {"label": "All reports", "url": "/admin/reports/", "icon": "file-text"}
    ]
    assert [a["label"] for a in alice.context["actions"]] == ["New order", "All reports"]
    assert alice.context["actions"][0]["url"] == "/admin/dashorder/create"
    assert (widget.key, widget.title, widget.lazy) == ("quick-actions", "Quick actions", False)
    assert widget.permission() is None


def test_a_widget_over_an_unregistered_report_is_refused() -> None:
    """
    Scenario: a widget over an unregistered report is refused
      Given OrderRevenueReport was not passed to register_report()
      When  register_widget(StatWidget(OrderRevenueReport)) is called
      Then  ValueError is raised naming the report
    """
    unregister_report(OrderRevenueReport)

    with pytest.raises(ValueError, match="OrderRevenueReport is not registered"):
        register_widget(StatWidget(OrderRevenueReport))

    assert registered_widgets() == []


def test_a_duplicate_widget_key_is_refused() -> None:
    """
    Scenario: a duplicate widget key is refused
      Given a widget with key "stat-orders-revenue" is registered
      When  another widget with the key "stat-orders-revenue" is registered
      Then  ValueError is raised
    """
    first = register_widget(StatWidget(OrderRevenueReport))

    with pytest.raises(ValueError, match="'stat-orders-revenue' is already registered"):
        register_widget(StatWidget(OrderRevenueReport, value="count_all"))

    assert register_widget(first) is first  # the same instance again is a no-op
    assert registered_widgets() == [first]


def test_a_stat_over_an_aggregate_without_totals_is_refused() -> None:
    """
    Scenario: a stat over an aggregate without totals is refused
      Given a registered report whose only aggregate is StringAggComma("sku")
      When  StatWidget(report) is constructed
      Then  ValueError is raised
    """
    with pytest.raises(ValueError, match="SkuListReport has no aggregate with totals"):
        StatWidget(SkuListReport)
    with pytest.raises(ValueError, match="has no totals"):
        StatWidget(SkuListReport, value=SkuListReport.values[0].name)
    with pytest.raises(ValueError, match="has no aggregate 'nope'"):
        StatWidget(OrderRevenueReport, value="nope")


def test_a_chart_over_a_report_without_a_dimension_is_refused() -> None:
    """
    Scenario: a chart over a report without a dimension is refused
      Given a registered report with no rows and no cols
      When  ChartWidget(report) is constructed
      Then  ValueError is raised
    """
    register_report(GrandTotalReport)

    with pytest.raises(ValueError, match="GrandTotalReport cannot be drawn as a chart"):
        ChartWidget(GrandTotalReport)


def test_stat_widget_takes_a_named_aggregate_key_title_and_span(tmp_path: Path) -> None:
    """
    Scenario: a stat names its aggregate, key, title and span
      Given StatWidget(OrderRevenueReport, value="count_all", key="orders", title="Orders", span=2)
      When  it renders over three orders
      Then  the value is 3 and the widget keeps the given key, title and span
    """
    mounted = mount(make_engine(tmp_path), auth=False)
    widget = register_widget(
        StatWidget(OrderRevenueReport, value="count_all", key="orders", title="Orders", span=2)
    )

    async def call(request: Request) -> WidgetBody:
        return await widget.render(request, mounted.admin)

    assert mounted.run(call).context["value"] == 3
    assert (widget.key, widget.title, widget.span) == ("orders", "Orders", 2)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"key": "Not Safe"}, "is not URL-safe"),
        ({"key": ""}, "needs a title"),
        ({"span": 0}, "span must be 1..4"),
        ({"span": 5}, "span must be 1..4"),
        ({"span": True}, "span must be 1..4"),
    ],
)
def test_a_widget_with_a_bad_key_title_or_span_is_refused(
    kwargs: dict[str, Any], message: str
) -> None:
    """
    Scenario: a bad key, an empty title or a span outside 1..4 is refused
      Given a custom widget with that key, title or span
      When  register_widget(widget) is called
      Then  ValueError is raised and nothing is registered
    """
    widget = TextWidget(kwargs.get("key", "a") or "a")
    if kwargs.get("key") == "":
        widget.title = ""
    widget.span = kwargs.get("span", 1)

    with pytest.raises(ValueError, match=message):
        register_widget(widget)

    assert registered_widgets() == []


def test_widgets_are_listed_in_registration_order_and_can_be_unregistered() -> None:
    """
    Scenario: the registry keeps registration order
      Given widgets b, a and c are registered in that order
      When  a is unregistered by instance and c by key
      Then  registered_widgets() is [b] and get_widget finds only b
    """
    b, a, c = (register_widget(TextWidget(key)) for key in ("b", "a", "c"))
    assert registered_widgets() == [b, a, c]
    assert get_widget("a") is a
    assert repr(a) == "TextWidget('a')"

    unregister_widget(a)
    unregister_widget("c")
    unregister_widget(a)  # no longer registered: a no-op
    unregister_widget(TextWidget("b"))  # another instance holding the key: a no-op

    assert registered_widgets() == [b]
    assert get_widget("a") is None
    assert (b.permission(), b.span, b.lazy, b.detail_label, b.body_testid) == (
        None,
        1,
        True,
        "Open",
        None,
    )
