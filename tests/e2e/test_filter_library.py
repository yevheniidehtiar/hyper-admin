"""End-to-end tests for the filter sidebar and saved views (H12, v0.5.6).

Spec: ``docs/specs/filter-library.md`` — one test per BDD scenario, named after
it. Designs: ``docs/design/system/components/FilterSidebar`` and
``SavedViews``. Inline ``# Given / # When / # Then`` comments are mandatory
(BDD conventions).

Selectors follow ``CLAUDE.md`` (E2E Selector Convention):
``get_by_role`` > ``get_by_label`` > ``get_by_text`` > ``get_by_test_id``.
``ha-*`` CSS classes are styling-only and never used as selectors.

The companion app (``tests.e2e.apps.filter_library``) seeds orders ORD-1..4
(alice owns 1 and 3, bob owns 2 and 4) and two shipments, one created today.
The fixture lives here, not in ``conftest.py``, so this module owns its app.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDER_LIST = "/admin/order"
SHIPMENT_LIST = "/admin/shipment"


@pytest.fixture
def filter_library_base_url(start_server: Callable[..., str]) -> str:
    """Start the filter-library fixture app and yield its base URL."""
    return start_server("tests.e2e.apps.filter_library")


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _open_orders(page: Page, base_url: str, username: str = "alice", query: str = "") -> None:
    _login(page, base_url, username)
    page.goto(f"{base_url}{ORDER_LIST}{query}")
    expect(page.get_by_test_id("filter-sidebar")).to_be_visible()


def _numbers(page: Page) -> list[str]:
    return [t.strip() for t in page.get_by_test_id("list-row").locator("td").all_inner_texts()]


def _apply(page: Page) -> None:
    page.get_by_test_id("filter-apply-btn").click()


def test_legacy_string_list_filter_classifies(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: legacy string list_filter still classifies fields
      Given AdminOptions(list_filter=["status", ...])
      When  the list view renders
      Then  the sidebar renders an auto-classified filter for that field
    """
    # Given an Order admin whose list_filter starts with the legacy string "status"
    # When the list view renders
    _open_orders(page, filter_library_base_url)

    # Then the sidebar carries a select for "status" offering "Any"
    sidebar = page.get_by_test_id("filter-sidebar")
    status = sidebar.get_by_label("Status")
    expect(status).to_be_visible()
    expect(status.get_by_role("option", name="Any")).to_have_count(1)


def test_daterange_filter_renders_two_inputs(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: explicit DateRangeFilter renders two date inputs
      Given AdminOptions(list_filter=[DateRangeFilter(field="created_on")])
      When  the user opens /admin/order
      Then  the sidebar exposes inputs created_on__gte and created_on__lte
    """
    # Given the Order admin with a DateRangeFilter on created_on
    # When the user opens the list
    _open_orders(page, filter_library_base_url)

    # Then both date inputs are in the sidebar under the stable test ids
    expect(page.get_by_test_id("filter-created_on-gte")).to_have_attribute(
        "name", "created_on__gte"
    )
    expect(page.get_by_test_id("filter-created_on-lte")).to_have_attribute(
        "name", "created_on__lte"
    )
    expect(page.get_by_test_id("filter-created_on-gte")).to_have_attribute("type", "date")


def test_applying_filter_swaps_tbody_with_push_url(
    page: Page, filter_library_base_url: str
) -> None:
    """
    Scenario: applying a filter swaps only the table body
      Given the same DateRangeFilter
      When  the user submits created_on__gte=2026-01-01
      Then  an HTMX GET /admin/order?created_on__gte=2026-01-01 is issued
      And   the response is a fragment containing only the new <tbody>
      And   the URL is updated via HX-Push-Url
    """
    # Given the unfiltered list showing all four orders
    _open_orders(page, filter_library_base_url)
    expect(page.get_by_test_id("list-row")).to_have_count(4)
    page.evaluate(
        "document.querySelector('[data-testid=list-table] thead').dataset.marker = 'kept'"
    )

    # When the user sets From to 2026-01-01 and applies
    page.get_by_test_id("filter-created_on-gte").fill("2026-01-01")
    with page.expect_response(
        lambda r: "created_on__gte=2026-01-01" in r.url and r.request.method == "GET"
    ) as response_info:
        _apply(page)

    # Then the response is the body fragment, not a page
    body = response_info.value.text()
    assert body.lstrip().startswith("<tbody")
    assert "<html" not in body
    # And only the 2026 orders remain, while the header element was never replaced
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    assert (
        page.evaluate("document.querySelector('[data-testid=list-table] thead').dataset.marker")
        == "kept"
    )
    # And the URL carries the filter state
    expect(page).to_have_url(re.compile(r"created_on__gte=2026-01-01"))


def test_isowner_filter_restricts_to_owned_rows(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: IsOwnerFilter restricts to objects the user owns
      Given IsOwnerFilter(owner_fields="created_by") and the user is alice
      When  the user toggles "Mine only" and submits
      Then  the request includes ?is_owner=1
      And   the result rows all have created_by == alice's user key
    """
    # Given alice on the unfiltered list
    _open_orders(page, filter_library_base_url)
    expect(page.get_by_test_id("list-row")).to_have_count(4)

    # When she switches "Mine only" on and applies
    page.get_by_test_id("filter-is_owner").check()
    with page.expect_response(lambda r: "is_owner=1" in r.url):
        _apply(page)

    # Then only ORD-1 and ORD-3 (created_by == "1") remain
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    rows = page.get_by_test_id("list-table")
    expect(rows).to_contain_text("ORD-1")
    expect(rows).to_contain_text("ORD-3")
    expect(rows).not_to_contain_text("ORD-2")
    expect(page).to_have_url(re.compile(r"is_owner=1"))


def test_current_period_default_redirects_on_first_load(
    page: Page, filter_library_base_url: str
) -> None:
    """
    Scenario: CurrentPeriodDefault preselects the current month on first load
      Given CurrentPeriodDefault(field="shipped_on", period="month") and no querystring
      When  the user opens /admin/shipment
      Then  the URL carries shipped_on__gte=<first of month>&shipped_on__lte=<today>
    """
    # Given a Shipment admin with the month default and no querystring
    _login(page, filter_library_base_url)

    # When the user opens the list
    page.goto(f"{filter_library_base_url}{SHIPMENT_LIST}")

    # Then the default is made explicit in the URL
    expect(page).to_have_url(
        re.compile(r"shipped_on__gte=\d{4}-\d{2}-01&shipped_on__lte=\d{4}-\d{2}-\d{2}")
    )
    # And only this month's shipment is listed, with the range inputs showing the default
    expect(page.get_by_test_id("list-row")).to_have_count(1)
    expect(page.get_by_test_id("list-table")).to_contain_text("S-NOW")
    expect(page.get_by_test_id("filter-shipped_on-gte")).to_have_value(
        re.compile(r"^\d{4}-\d{2}-01$")
    )


def test_save_current_view_creates_row(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: saving the current filter set creates a SavedView row
      Given the user has filters applied
      When  the user posts /admin/order/saved-views with name="Mine"
      Then  a saved view exists with that name and the filter querystring
      And   the sidebar shows "Mine" as a clickable view
    """
    # Given alice with "Mine only" applied
    _open_orders(page, filter_library_base_url, query="?is_owner=1")
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    expect(page.get_by_test_id("saved-views")).to_contain_text("Save the filters you use often.")

    # When she names the current filters and saves the view
    page.get_by_test_id("save-view-btn").click()
    page.get_by_label("Name").fill("Mine")
    page.get_by_role("button", name="Save view").last.click()

    # Then the saved view is listed and clickable, and marked active
    view = page.get_by_test_id("saved-views").get_by_role("link", name="Mine")
    expect(view).to_be_visible()
    expect(view).to_have_attribute("aria-current", "true")
    # And the API lists it with the stored querystring
    listing = page.request.get(f"{filter_library_base_url}{ORDER_LIST}/saved-views").json()
    assert [(v["name"], v["querystring"]) for v in listing["views"]] == [("Mine", "is_owner=1")]


def test_loading_saved_view_applies_querystring(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: loading a saved view applies its querystring
      Given alice has a saved view "Mine"
      When  alice clicks the saved view
      Then  the list view is requested with that view's querystring
      And   the resulting table body matches the saved filter
    """
    # Given alice's saved view over "Mine only", and the unfiltered list open
    _open_orders(page, filter_library_base_url, query="?is_owner=1")
    page.get_by_test_id("save-view-btn").click()
    page.get_by_label("Name").fill("Mine")
    page.get_by_role("button", name="Save view").last.click()
    page.goto(f"{filter_library_base_url}{ORDER_LIST}")
    expect(page.get_by_test_id("list-row")).to_have_count(4)

    # When she clicks the saved view
    page.get_by_test_id("saved-views").get_by_role("link", name="Mine").click()

    # Then the list is requested with the saved querystring
    expect(page).to_have_url(re.compile(r"is_owner=1"))
    # And the rows match the saved filter
    expect(page.get_by_test_id("list-row")).to_have_count(2)
    expect(page.get_by_test_id("filter-is_owner")).to_be_checked()


def test_saved_views_are_scoped_per_user(page: Page, filter_library_base_url: str) -> None:
    """
    Scenario: another user does not see alice's saved views
      Given alice has a saved view "Mine" and bob is logged in
      When  bob opens /admin/order
      Then  the saved-views panel does not list "Mine"
    """
    # Given alice saved a view
    _open_orders(page, filter_library_base_url, query="?is_owner=1")
    page.get_by_test_id("save-view-btn").click()
    page.get_by_label("Name").fill("Mine")
    page.get_by_role("button", name="Save view").last.click()
    expect(page.get_by_test_id("saved-views").get_by_role("link", name="Mine")).to_be_visible()

    # When bob signs in and opens the same list
    page.context.clear_cookies()
    _open_orders(page, filter_library_base_url, username="bob")

    # Then his panel is empty of alice's view
    panel = page.get_by_test_id("saved-views")
    expect(panel).to_be_visible()
    expect(panel.get_by_role("link", name="Mine")).to_have_count(0)
    expect(panel).to_contain_text("Save the filters you use often.")


def test_deleting_saved_view_asks_first_then_removes_it(
    page: Page, filter_library_base_url: str
) -> None:
    """
    Scenario: deleting a saved view asks for confirmation, then removes only that view
      Given alice has a saved view "Mine"
      When  she opens its actions, chooses Delete and confirms
      Then  the view leaves the panel and the API no longer lists it
    """
    # Given alice's saved view
    _open_orders(page, filter_library_base_url, query="?is_owner=1")
    page.get_by_test_id("save-view-btn").click()
    page.get_by_label("Name").fill("Mine")
    page.get_by_role("button", name="Save view").last.click()
    panel = page.get_by_test_id("saved-views")
    expect(panel.get_by_role("link", name="Mine")).to_be_visible()

    # When she chooses Delete… from the view's actions
    page.get_by_label("Actions for view Mine").click()
    page.get_by_role("button", name="Delete…").click()

    # Then a confirm dialog names the view, and nothing is deleted yet
    dialog = page.get_by_role("alertdialog")
    expect(dialog).to_contain_text("Delete the view “Mine”?")
    assert (
        len(page.request.get(f"{filter_library_base_url}{ORDER_LIST}/saved-views").json()["views"])
        == 1
    )

    # When she confirms
    dialog.get_by_role("button", name="Delete view").click()

    # Then the view is gone from the panel and from the API
    expect(panel.get_by_role("link", name="Mine")).to_have_count(0)
    assert (
        page.request.get(f"{filter_library_base_url}{ORDER_LIST}/saved-views").json()["views"] == []
    )
