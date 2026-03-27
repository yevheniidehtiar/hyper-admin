"""End-to-end tests for custom action buttons on the detail view."""

import re

from playwright.sync_api import Page, expect


def test_action_button_visible_on_detail(page: Page, demo_base_url: str) -> None:
    """A registered @action button is visible on the model detail page."""
    page.goto(demo_base_url + "/admin/user")
    page.get_by_test_id("list-row").first.get_by_test_id("row-view-link").click()

    expect(page).to_have_url(re.compile(r"/admin/user/\d+$"))
    expect(page.get_by_test_id("action-buttons")).to_be_visible()
    expect(page.get_by_test_id("action-deactivate-btn")).to_be_visible()
    expect(page.get_by_test_id("action-deactivate-btn")).to_have_text("Deactivate")


def test_action_triggers_and_redirects_to_list(page: Page, demo_base_url: str) -> None:
    """Clicking an action button and accepting the confirm dialog redirects to the list."""
    page.goto(demo_base_url + "/admin/user")
    page.get_by_test_id("list-row").first.get_by_test_id("row-view-link").click()

    expect(page).to_have_url(re.compile(r"/admin/user/\d+$"))

    page.on("dialog", lambda d: d.accept())
    page.get_by_test_id("action-deactivate-btn").click()

    expect(page).to_have_url(re.compile(r"/admin/user$"))
    expect(page.get_by_test_id("list-table")).to_be_visible()


def test_action_confirm_cancel_stays_on_detail(page: Page, demo_base_url: str) -> None:
    """Dismissing the confirm dialog leaves the user on the detail page."""
    page.goto(demo_base_url + "/admin/user")
    page.get_by_test_id("list-row").first.get_by_test_id("row-view-link").click()

    detail_url = page.url
    expect(page).to_have_url(re.compile(r"/admin/user/\d+$"))

    page.on("dialog", lambda d: d.dismiss())
    page.get_by_test_id("action-deactivate-btn").click()

    expect(page).to_have_url(detail_url)
    expect(page.get_by_test_id("action-deactivate-btn")).to_be_visible()
