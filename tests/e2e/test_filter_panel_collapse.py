"""E2E: the filter panel beside a list collapses so the table gets the whole width.

One test per scenario, against the ERP demo app (``examples.erp.main``,
superuser ``admin``/``admin``). The invoice table is wider than the space left
next to the 18rem filter panel on a laptop, so its last columns (Total Amount
and the delete buttons) scroll out of view while the panel is open.

* collapsing the filter panel gives the table the whole width
* the filter panel starts collapsed below 1440px
* the expanded state persists across a reload
* the Filters button shows the active filter count
* the Filters button works from the keyboard
* the filter panel still toggles when storage is blocked
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator

LAPTOP = {"width": 1280, "height": 800}
DESKTOP = {"width": 1440, "height": 900}


@pytest.fixture
def erp_url(start_server: Callable[..., str]) -> str:
    """Start the ERP demo app and return its base URL."""
    return start_server("examples.erp.main", ready_path="/")


def _login(page: Page, base_url: str) -> None:
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")


def _filters_button(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^Filters( \d+)?$"))


def _table_scrolls_sideways(page: Page) -> bool:
    """Whether any box around the list table is narrower than the table itself."""
    return page.get_by_test_id("list-table").evaluate(
        """(table) => {
            for (let node = table; node; node = node.parentElement) {
                if (node.scrollWidth > node.clientWidth + 1) return true;
            }
            return false;
        }"""
    )


def _fully_in_view(page: Page, locator: Locator) -> bool:
    """Whether the element lies entirely inside the viewport and its scroll boxes."""
    return locator.evaluate(
        """(el) => {
            const box = el.getBoundingClientRect();
            for (let node = el.parentElement; node; node = node.parentElement) {
                if (getComputedStyle(node).overflowX === 'visible') continue;
                const clip = node.getBoundingClientRect();
                if (box.left < clip.left - 1 || box.right > clip.right + 1) return false;
            }
            return box.left >= 0 && box.right <= window.innerWidth;
        }"""
    )


def test_collapsing_the_filter_panel_gives_the_table_the_whole_width(
    page: Page, erp_url: str
) -> None:
    """
    Scenario: collapsing the filter panel gives the table the whole width
      Given the invoice list on a 1440px screen with the filter panel expanded
      When  the user clicks Filters
      Then  the filter panel hides and the table gets wider
      And   Total Amount and the delete buttons show in full without a horizontal scroll
    """
    # Given the invoice list on a 1440px screen with the filter panel expanded
    page.set_viewport_size(DESKTOP)
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice")
    panel = page.get_by_test_id("filter-sidebar")
    expect(panel).to_be_visible()
    expect(_filters_button(page)).to_have_attribute("aria-expanded", "true")
    table = page.get_by_test_id("list-table")
    width_before = page.get_by_test_id("list-table").evaluate(
        "(t) => t.parentElement.getBoundingClientRect().width"
    )

    # When the user clicks Filters
    _filters_button(page).click()

    # Then the filter panel hides and the table gets wider
    expect(panel).to_be_hidden()
    expect(_filters_button(page)).to_have_attribute("aria-expanded", "false")
    width_after = table.evaluate("(t) => t.parentElement.getBoundingClientRect().width")
    assert width_after > width_before + 200

    # And Total Amount and the delete buttons show in full without a horizontal scroll
    assert not _table_scrolls_sideways(page)
    assert _fully_in_view(page, page.get_by_role("columnheader", name="Total Amount"))
    assert _fully_in_view(page, page.get_by_test_id("row-delete-btn").first)


def test_the_filter_panel_starts_collapsed_below_1440px(page: Page, erp_url: str) -> None:
    """
    Scenario: the filter panel starts collapsed below 1440px
      Given a viewer who never toggled the filter panel, on a 1280px laptop
      When  they open the invoice list
      Then  the filter panel is collapsed and the Filters button says so
      And   the table shows every column without a horizontal scroll
    """
    # Given a viewer who never toggled the filter panel, on a 1280px laptop
    page.set_viewport_size(LAPTOP)
    _login(page, erp_url)

    # When they open the invoice list
    page.goto(erp_url + "/admin/invoice")

    # Then the filter panel is collapsed and the Filters button says so
    expect(page.get_by_test_id("filter-sidebar")).to_be_hidden()
    expect(_filters_button(page)).to_have_attribute("aria-expanded", "false")
    expect(_filters_button(page)).to_have_attribute("aria-controls", "filter-sidebar")

    # And the table shows every column without a horizontal scroll
    assert not _table_scrolls_sideways(page)
    assert _fully_in_view(page, page.get_by_test_id("row-delete-btn").first)


def test_the_expanded_state_persists_across_a_reload(page: Page, erp_url: str) -> None:
    """
    Scenario: the expanded state persists across a reload
      Given the invoice list on a 1280px laptop with the filter panel collapsed
      When  the user expands it with Filters and reloads the page
      Then  the filter panel is still expanded
    """
    # Given the invoice list on a 1280px laptop with the filter panel collapsed
    page.set_viewport_size(LAPTOP)
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice")
    panel = page.get_by_test_id("filter-sidebar")
    expect(panel).to_be_hidden()

    # When the user expands it with Filters and reloads the page
    _filters_button(page).click()
    expect(panel).to_be_visible()
    page.reload()

    # Then the filter panel is still expanded
    expect(panel).to_be_visible()
    expect(_filters_button(page)).to_have_attribute("aria-expanded", "true")


def test_the_filters_button_shows_the_active_filter_count(page: Page, erp_url: str) -> None:
    """
    Scenario: the Filters button shows the active filter count
      Given a 1280px laptop where the filter panel is collapsed
      When  the user opens the invoice list filtered to Paid invoices
      Then  the Filters button carries a badge with 1
    """
    # Given a 1280px laptop where the filter panel is collapsed
    page.set_viewport_size(LAPTOP)
    _login(page, erp_url)

    # When the user opens the invoice list filtered to Paid invoices
    page.goto(erp_url + "/admin/invoice?filter_status=PAID")

    # Then the Filters button carries a badge with 1
    expect(page.get_by_test_id("filter-sidebar")).to_be_hidden()
    expect(_filters_button(page).get_by_test_id("filters-toggle-count")).to_have_text("1")


def test_the_filters_button_works_from_the_keyboard(page: Page, erp_url: str) -> None:
    """
    Scenario: the Filters button works from the keyboard
      Given the invoice list on a 1280px laptop with the filter panel collapsed
      When  the user focuses Filters and presses Enter
      Then  the filter panel expands and Filters keeps a visible focus ring
    """
    # Given the invoice list on a 1280px laptop with the filter panel collapsed
    page.set_viewport_size(LAPTOP)
    _login(page, erp_url)
    page.goto(erp_url + "/admin/invoice")
    button = _filters_button(page)

    # When the user focuses Filters and presses Enter
    page.get_by_test_id("search-input").focus()
    page.keyboard.press("Tab")
    expect(button).to_be_focused()
    page.keyboard.press("Enter")

    # Then the filter panel expands and Filters keeps a visible focus ring
    expect(page.get_by_test_id("filter-sidebar")).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")
    outline = button.evaluate("(b) => getComputedStyle(b).outlineStyle")
    assert outline != "none"


def test_the_filter_panel_still_toggles_when_storage_is_blocked(page: Page, erp_url: str) -> None:
    """
    Scenario: the filter panel still toggles when storage is blocked
      Given a browser that throws on every localStorage access, on a 1280px laptop
      When  the user opens the invoice list and clicks Filters
      Then  the filter panel expands
    """
    # Given a browser that throws on every localStorage access, on a 1280px laptop
    page.set_viewport_size(LAPTOP)
    _login(page, erp_url)
    page.add_init_script(
        """Object.defineProperty(window, 'localStorage', {
            get() { throw new DOMException('blocked', 'SecurityError'); },
        });"""
    )

    # When the user opens the invoice list and clicks Filters
    page.goto(erp_url + "/admin/invoice")
    panel = page.get_by_test_id("filter-sidebar")
    expect(panel).to_be_hidden()
    _filters_button(page).click()

    # Then the filter panel expands
    expect(panel).to_be_visible()
