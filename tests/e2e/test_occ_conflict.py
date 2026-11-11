"""E2E: optimistic concurrency control, two sessions editing one record (#321).

Spec: ``docs/specs/realtime-occ.md``. One test per scenario, against
:mod:`tests.e2e.apps.occ_conflict`: ``Order`` enforces OCC (row 42 starts at
version 3), ``Tag`` leaves it off. "Alice" and "Bob" are two browser contexts
signed in as the same admin account.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDER_EDIT = "/admin/order/42/edit"
ORDER_LIST = "/admin/order"


@pytest.fixture
def occ_base_url(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.occ_conflict` and return its base URL."""
    return start_server("tests.e2e.apps.occ_conflict")


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _second_session(browser: Browser, base_url: str) -> Page:
    """A second, independent browser context signed in to the same admin."""
    page = browser.new_context().new_page()
    _login(page, base_url)
    return page


def _save_customer(page: Page, base_url: str, customer: str) -> None:
    page.goto(base_url + ORDER_EDIT)
    page.get_by_label("Customer").fill(customer)
    page.get_by_role("button", name="Update").click()
    expect(page).to_have_url(base_url + ORDER_LIST)


def test_stale_save_shows_conflict_dialog_and_keeps_the_row(
    page: Page, browser: Browser, occ_base_url: str
) -> None:
    # Given Alice opened order #42 (version 3) and Bob then saved it
    _login(page, occ_base_url)
    page.goto(occ_base_url + ORDER_EDIT)
    bob = _second_session(browser, occ_base_url)
    _save_customer(bob, occ_base_url, "Bob's Co")

    # When Alice saves her own change from the now-stale form
    page.get_by_label("Customer").fill("Alice's Co")
    page.get_by_role("button", name="Update").click()

    # Then the conflict dialog compares her edit with the current value
    dialog = page.get_by_test_id("conflict-dialog")
    expect(dialog).to_be_visible()
    expect(page.get_by_test_id("conflict-mine-customer")).to_have_text("Alice's Co")
    expect(page.get_by_test_id("conflict-current-customer")).to_have_text("Bob's Co")
    # And the row still holds Bob's value
    page.goto(occ_base_url + ORDER_EDIT)
    expect(page.get_by_label("Customer")).to_have_value("Bob's Co")


def test_discard_my_edits_opens_a_fresh_form(
    page: Page, browser: Browser, occ_base_url: str
) -> None:
    # Given Alice is looking at the conflict dialog after a stale save
    _login(page, occ_base_url)
    page.goto(occ_base_url + ORDER_EDIT)
    _save_customer(_second_session(browser, occ_base_url), occ_base_url, "Bob's Co")
    page.get_by_label("Customer").fill("Alice's Co")
    page.get_by_role("button", name="Update").click()
    expect(page.get_by_test_id("conflict-dialog")).to_be_visible()

    # When she chooses "Discard my edits"
    page.get_by_test_id("conflict-discard").click()

    # Then a fresh edit form shows the current values
    expect(page).to_have_url(occ_base_url + ORDER_EDIT)
    expect(page.get_by_label("Customer")).to_have_value("Bob's Co")
    expect(page.get_by_test_id("conflict-dialog")).to_have_count(0)


def test_override_anyway_saves_against_the_current_version(
    page: Page, browser: Browser, occ_base_url: str
) -> None:
    # Given Alice is looking at the conflict dialog after a stale save
    _login(page, occ_base_url)
    page.goto(occ_base_url + ORDER_EDIT)
    _save_customer(_second_session(browser, occ_base_url), occ_base_url, "Bob's Co")
    page.get_by_label("Customer").fill("Alice's Co")
    page.get_by_role("button", name="Update").click()
    expect(page.get_by_test_id("conflict-dialog")).to_be_visible()

    # When she chooses "Override anyway"
    page.get_by_test_id("conflict-override").click()

    # Then her value is saved and she lands on the list
    expect(page).to_have_url(occ_base_url + ORDER_LIST)
    page.goto(occ_base_url + ORDER_EDIT)
    expect(page.get_by_label("Customer")).to_have_value("Alice's Co")


def test_stale_inline_cell_save_is_marked_stale(
    page: Page, browser: Browser, occ_base_url: str
) -> None:
    # Given Alice opened the inline editor for order #42's customer
    _login(page, occ_base_url)
    page.goto(occ_base_url + ORDER_LIST)
    page.get_by_test_id("cell-edit-customer-42").click()
    expect(page.get_by_test_id("cell-editor-customer-42")).to_be_visible()
    # And Bob saved the order in the meantime
    _save_customer(_second_session(browser, occ_base_url), occ_base_url, "Bob's Co")

    # When Alice saves her inline edit
    page.get_by_role("textbox", name="Customer", exact=True).fill("Alicia")
    page.get_by_role("textbox", name="Customer", exact=True).press("Enter")

    # Then the cell shows Bob's value with a stale marker
    expect(page.get_by_test_id("cell-stale-customer-42")).to_be_visible()
    expect(page.get_by_test_id("cell-value-customer-42")).to_have_text("Bob's Co")
    # And Refresh re-opens the editor on the current value
    page.get_by_test_id("cell-refresh-customer-42").click()
    expect(page.get_by_role("textbox", name="Customer", exact=True)).to_have_value("Bob's Co")


def test_model_without_occ_is_last_write_wins(
    page: Page, browser: Browser, occ_base_url: str
) -> None:
    # Given Alice opened tag #1 and Bob saved it afterwards (OCC is off for Tag)
    _login(page, occ_base_url)
    page.goto(occ_base_url + "/admin/tag/1/edit")
    bob = _second_session(browser, occ_base_url)
    bob.goto(occ_base_url + "/admin/tag/1/edit")
    bob.get_by_label("Label").fill("blue")
    bob.get_by_role("button", name="Update").click()
    expect(bob).to_have_url(occ_base_url + "/admin/tag")

    # When Alice saves from her older form
    page.get_by_label("Label").fill("green")
    page.get_by_role("button", name="Update").click()

    # Then her save wins and no conflict dialog appears
    expect(page).to_have_url(occ_base_url + "/admin/tag")
    expect(page.get_by_test_id("conflict-dialog")).to_have_count(0)
    page.goto(occ_base_url + "/admin/tag/1/edit")
    expect(page.get_by_label("Label")).to_have_value("green")
