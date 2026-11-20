"""E2E: the reports plugin's dashboard (story #469, epic #422).

SDD ``docs/specs/dashboard-builder.md``. Runs against :mod:`tests.e2e.apps.dashboard_builder`:
five widgets (a revenue stat, a chart, a payroll stat, quick actions and a widget that always
fails) with the layout table created. One test per scenario, named after it. Uses
accessibility-first selectors per CLAUDE.md E2E Selector Convention.
"""

from playwright.sync_api import Browser, Page, expect

REVENUE = "widget-stat-orders-revenue"
CHART = "widget-chart-orders-by-month"
PAYROLL = "widget-stat-payroll-total"
ACTIONS = "widget-quick-actions"
BROKEN = "widget-broken"
DEFAULT_ORDER = [REVENUE, CHART, PAYROLL, ACTIONS, BROKEN]


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _cards(page: Page) -> list[str | None]:
    """The cards' test ids, in the order they are on the page."""
    grid = page.get_by_test_id("dashboard-grid")
    return [card.get_attribute("data-testid") for card in grid.get_by_role("article").all()]


def _expect_order(page: Page, order: list[str]) -> None:
    cards = page.get_by_test_id("dashboard-grid").get_by_role("article")
    expect(cards).to_have_count(len(order))
    for index, testid in enumerate(order):
        expect(cards.nth(index)).to_have_attribute("data-testid", testid)


def _move_chart_up(page: Page) -> None:
    """Alice's usual change: the chart card goes first."""
    page.get_by_test_id(CHART).get_by_test_id("widget-move-up").click()
    _expect_order(page, [CHART, REVENUE, PAYROLL, ACTIONS, BROKEN])


def test_dashboard_replaces_the_welcome_page_when_widgets_are_registered(
    page: Page, dashboard_base_url: str
) -> None:
    """Scenario: dashboard replaces the welcome page when widgets are registered."""
    # Given the dashboard app with registered widgets

    # When alice opens {prefix}/
    _login(page, dashboard_base_url, "alice")

    # Then dashboard-grid is visible
    expect(page.get_by_test_id("dashboard-grid")).to_be_visible()
    expect(page.get_by_role("heading", name="Dashboard", level=1)).to_be_visible()
    # And the text "Welcome to HyperAdmin Dashboard" is not on the page
    expect(page.get_by_text("Welcome to HyperAdmin Dashboard")).to_have_count(0)
    assert _cards(page) == DEFAULT_ORDER


def test_stat_widget_shows_the_grand_total_of_its_report_aggregate(
    page: Page, dashboard_base_url: str
) -> None:
    """Scenario: stat widget shows the grand total of its report aggregate."""
    # Given Orders with amounts 100, 200 and 300

    # When alice opens the dashboard
    _login(page, dashboard_base_url, "alice")

    # Then stat-stat-orders-revenue shows "600"
    expect(page.get_by_test_id("stat-stat-orders-revenue")).to_have_text("600")
    card = page.get_by_test_id(REVENUE)
    expect(card.get_by_role("heading", name="Revenue")).to_be_visible()
    expect(card.get_by_role("link", name="Open report")).to_have_attribute(
        "href", "/admin/reports/orders-revenue/"
    )


def test_chart_widget_embeds_the_report_chart_fragment(page: Page, dashboard_base_url: str) -> None:
    """Scenario: chart widget embeds the report chart fragment."""
    # Given a ChartWidget over "orders-by-month"

    # When alice opens the dashboard
    _login(page, dashboard_base_url, "alice")

    # Then the card widget-chart-orders-by-month contains report-chart
    chart = page.get_by_test_id(CHART).get_by_test_id("report-chart")
    expect(chart).to_be_visible()
    expect(chart.get_by_test_id("chart-frame")).to_be_visible()
    expect(chart.get_by_text("Show as table")).to_be_visible()
    expect(chart.get_by_test_id("widget-loading")).to_have_count(0)


def test_quick_actions_widget_shows_only_the_actions_the_user_may_use(
    page: Page, dashboard_base_url: str
) -> None:
    """Scenario: quick actions widget shows only the actions the user may use."""
    # Given user "viewer" lacks add_order

    # When viewer opens the dashboard
    _login(page, dashboard_base_url, "viewer")

    # Then the quick actions card has the link "All reports"
    card = page.get_by_test_id(ACTIONS)
    expect(card.get_by_role("link", name="All reports")).to_be_visible()
    # And it has no link "New order"
    expect(card.get_by_role("link", name="New order")).to_have_count(0)


def test_widgets_the_user_may_not_view_are_not_shown(page: Page, dashboard_base_url: str) -> None:
    """Scenario: widgets the user may not view are not shown."""
    # Given user "viewer" lacks view_report_payroll_total

    # When viewer opens the dashboard
    _login(page, dashboard_base_url, "viewer")

    # Then the card widget-stat-payroll-total is not on the page
    expect(page.get_by_test_id(REVENUE)).to_be_visible()
    expect(page.get_by_test_id(PAYROLL)).to_have_count(0)
    assert _cards(page) == [REVENUE, CHART, ACTIONS, BROKEN]


def test_failing_widget_shows_an_error_state_and_the_others_render(
    page: Page, dashboard_base_url: str
) -> None:
    """Scenario: failing widget shows an error state and the others render."""
    # Given the custom widget "broken" raises in render()

    # When alice opens the dashboard
    _login(page, dashboard_base_url, "alice")

    # Then the card widget-broken shows widget-error with a "Retry" button
    broken = page.get_by_test_id(BROKEN)
    expect(broken.get_by_test_id("widget-error")).to_be_visible()
    expect(broken.get_by_text("Widget unavailable")).to_be_visible()
    expect(broken.get_by_role("button", name="Retry")).to_be_visible()
    # And stat-stat-orders-revenue shows "600"
    expect(page.get_by_test_id("stat-stat-orders-revenue")).to_have_text("600")


def test_drag_and_drop_saves_the_new_order(page: Page, dashboard_base_url: str) -> None:
    """Scenario: drag and drop saves the new order."""
    # Given alice sees the default order
    _login(page, dashboard_base_url, "alice")
    _expect_order(page, DEFAULT_ORDER)
    handle = page.get_by_test_id(BROKEN).get_by_test_id("widget-drag-handle")
    expect(handle).to_be_visible()

    # When alice drags the last card's handle onto the first card
    with page.expect_response(lambda r: r.url.endswith("/admin/dashboard/layout")) as saved:
        handle.drag_to(page.get_by_test_id(REVENUE), target_position={"x": 20, "y": 20})
    assert saved.value.status == 204
    _expect_order(page, [BROKEN, REVENUE, CHART, PAYROLL, ACTIONS])

    # Then after a reload the last card is first
    page.reload()
    _expect_order(page, [BROKEN, REVENUE, CHART, PAYROLL, ACTIONS])


def test_move_up_button_reorders_without_drag_and_drop(page: Page, dashboard_base_url: str) -> None:
    """Scenario: move up button reorders without drag and drop."""
    # Given alice sees cards [A, B, C]
    _login(page, dashboard_base_url, "alice")
    _expect_order(page, DEFAULT_ORDER)

    # When alice focuses B's "Move up" button and presses Enter
    page.get_by_test_id(CHART).get_by_role("button", name="Move Orders by month up").focus()
    page.keyboard.press("Enter")

    # Then the cards are [B, A, C]
    _expect_order(page, [CHART, REVENUE, PAYROLL, ACTIONS, BROKEN])
    # And B's "Move up" button is focused
    expect(page.get_by_test_id(CHART).get_by_test_id("widget-move-up")).to_be_focused()
    expect(page.get_by_test_id("dashboard-live")).to_have_text(
        "Moved Orders by month to position 1 of 5"
    )
    page.reload()
    _expect_order(page, [CHART, REVENUE, PAYROLL, ACTIONS, BROKEN])


def test_layout_is_per_user(page: Page, browser: Browser, dashboard_base_url: str) -> None:
    """Scenario: layout is per user."""
    # Given alice moved a card
    _login(page, dashboard_base_url, "alice")
    _move_chart_up(page)

    # When bob opens the dashboard
    context = browser.new_context()
    try:
        bob = context.new_page()
        _login(bob, dashboard_base_url, "bob")

        # Then bob sees the default order
        _expect_order(bob, DEFAULT_ORDER)
    finally:
        context.close()


def test_reset_returns_to_the_default_order(page: Page, dashboard_base_url: str) -> None:
    """Scenario: reset returns to the default order."""
    # Given alice moved a card
    _login(page, dashboard_base_url, "alice")
    _move_chart_up(page)

    # When alice clicks "Reset layout"
    page.get_by_role("button", name="Reset layout").click()

    # Then alice sees the default order
    _expect_order(page, DEFAULT_ORDER)
    page.reload()
    _expect_order(page, DEFAULT_ORDER)


def test_user_with_no_visible_widgets_sees_an_empty_state(
    page: Page, dashboard_base_url: str
) -> None:
    """Scenario: user with no visible widgets sees an empty state."""
    # Given user "nobody" holds no report permission

    # When nobody opens the dashboard
    _login(page, dashboard_base_url, "nobody")

    # Then dashboard-empty is visible
    expect(page.get_by_test_id("dashboard-empty")).to_be_visible()
    expect(page.get_by_test_id("dashboard-grid")).to_have_count(0)
    expect(page.get_by_role("button", name="Reset layout")).to_have_count(0)


def test_a_failed_save_puts_the_cards_back(page: Page, dashboard_base_url: str) -> None:
    """Scenario: a failed save puts the cards back (story #466)."""
    # Given alice sees [A, B, C] and the layout POST answers 400
    _login(page, dashboard_base_url, "alice")
    _expect_order(page, DEFAULT_ORDER)
    page.route("**/admin/dashboard/layout", lambda route: route.fulfill(status=400, body=""))

    # When alice drags C onto the first position
    with page.expect_response(lambda r: r.url.endswith("/admin/dashboard/layout")) as refused:
        page.get_by_test_id(BROKEN).get_by_test_id("widget-drag-handle").drag_to(
            page.get_by_test_id(REVENUE), target_position={"x": 20, "y": 20}
        )
    assert refused.value.status == 400

    # Then the grid shows [A, B, C] again
    _expect_order(page, DEFAULT_ORDER)
    # And an error toast says the order could not be saved
    toast = page.get_by_test_id("dashboard-error-toast")
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("The order could not be saved")
    page.unroute("**/admin/dashboard/layout")
    page.reload()
    _expect_order(page, DEFAULT_ORDER)
