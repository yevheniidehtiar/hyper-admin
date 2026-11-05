"""E2E: list keyboard navigation and the shortcuts overlay (st-v059-kbd-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Keyboard (kbd-02)"). One test per
story scenario, against :mod:`tests.e2e.apps.list_rows`: three orders (#42, #43,
#44) with a bulk "Archive" action; ``alice`` holds every Order permission, so the
row links open the edit page.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDERS = "/admin/order"


@pytest.fixture
def keys_base_url(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.list_rows` and return its base URL."""
    return start_server("tests.e2e.apps.list_rows")


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _open_orders(page: Page, base_url: str) -> None:
    page.goto(base_url + ORDERS)
    expect(page.get_by_test_id("row-link")).to_have_count(3)


def test_j_k_move_between_rows_and_enter_opens_one(page: Page, keys_base_url: str) -> None:
    """
    Scenario: j/k move between rows and Enter opens one
      Given a list of 3 orders
      When  the user presses j twice and then Enter
      Then  the second row's record opens
    """
    # Given a list of 3 orders
    _login(page, keys_base_url)
    _open_orders(page, keys_base_url)

    # When the user presses j twice and then Enter
    page.keyboard.press("j")
    expect(page.get_by_test_id("row-link").nth(0)).to_be_focused()
    page.keyboard.press("j")
    expect(page.get_by_test_id("row-link").nth(1)).to_be_focused()
    page.keyboard.press("Enter")

    # Then the second row's record opens
    expect(page).to_have_url(f"{keys_base_url}{ORDERS}/43/edit")


def test_x_selects_the_focused_row(page: Page, keys_base_url: str) -> None:
    """
    Scenario: x selects the focused row
      Given a list with a bulk action and row 1 focused
      When  the user presses x
      Then  row 1's checkbox is checked and the bulk bar shows "1 selected"
    """
    # Given a list with a bulk action and row 1 focused
    _login(page, keys_base_url)
    _open_orders(page, keys_base_url)
    page.keyboard.press("j")
    first = page.get_by_test_id("list-row").nth(0)
    expect(first.get_by_test_id("row-link")).to_be_focused()

    # When the user presses x
    page.keyboard.press("x")

    # Then row 1's checkbox is checked and the bulk bar shows "1 selected"
    expect(first.get_by_test_id("bulk-checkbox")).to_be_checked()
    expect(page.get_by_test_id("bulk-count")).to_have_text("1 selected")


def test_single_key_shortcuts_can_be_turned_off(page: Page, keys_base_url: str) -> None:
    """
    Scenario: single-key shortcuts can be turned off
      Given the user turns shortcuts off in the ? overlay
      When  the user presses j on a list
      Then  nothing happens and Cmd+K still opens the palette
    """
    # Given the user turns shortcuts off in the ? overlay
    _login(page, keys_base_url)
    _open_orders(page, keys_base_url)
    page.keyboard.press("?")
    overlay = page.get_by_test_id("shortcuts-overlay")
    expect(overlay).to_be_visible()
    toggle = page.get_by_role("switch", name="Single-key shortcuts")
    expect(toggle).to_be_checked()
    toggle.click()
    expect(toggle).not_to_be_checked()
    page.keyboard.press("Escape")
    expect(overlay).to_be_hidden()

    # When the user presses j on a list
    page.keyboard.press("j")

    # Then nothing happens
    for link in page.get_by_test_id("row-link").all():
        expect(link).not_to_be_focused()
    # And Cmd+K still opens the palette
    page.keyboard.press("ControlOrMeta+k")
    expect(page.get_by_test_id("command-palette")).to_be_visible()


def test_typing_in_the_search_box_is_not_hijacked(page: Page, keys_base_url: str) -> None:
    """
    Scenario: typing in the search box is not hijacked
      Given focus is in the list search input
      When  the user types "jack"
      Then  the input contains "jack" and no row is focused
    """
    # Given focus is in the list search input
    _login(page, keys_base_url)
    _open_orders(page, keys_base_url)
    search = page.get_by_test_id("search-input")
    search.click()

    # When the user types "jack"
    page.keyboard.type("jack")

    # Then the input contains "jack" and no row is focused
    expect(search).to_have_value("jack")
    expect(search).to_be_focused()
    for link in page.get_by_test_id("row-link").all():
        expect(link).not_to_be_focused()
