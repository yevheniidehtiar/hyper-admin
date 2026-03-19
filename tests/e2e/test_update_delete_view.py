"""End-to-end tests for update and delete view functionality."""

import re

from playwright.sync_api import Page, expect


def test_edit_link_navigates_to_update_form(page: Page, demo_base_url: str) -> None:
    """Edit link in the list table opens the update form pre-filled with existing values."""
    page.goto(demo_base_url + "/admin/user")

    page.get_by_test_id("list-row").first.get_by_test_id("row-edit-link").click()

    expect(page).to_have_url(re.compile(r"/edit$"))
    expect(page.get_by_test_id("model-form")).to_be_visible()
    expect(page.get_by_label("Name*")).not_to_be_empty()


def test_update_form_submits_successfully(page: Page, demo_base_url: str) -> None:
    """Submitting the update form with valid data saves and returns to the list."""
    page.goto(demo_base_url + "/admin/user")

    page.get_by_test_id("list-row").first.get_by_test_id("row-edit-link").click()
    expect(page.get_by_test_id("model-form")).to_be_visible()

    page.get_by_label("Name*").fill("Alice Updated")
    page.get_by_role("button", name="Update").click()

    expect(page).to_have_url(re.compile(r"/admin/user$"))
    expect(page.get_by_test_id("list-table")).to_contain_text("Alice Updated")


def test_update_form_shows_validation_errors(page: Page, demo_base_url: str) -> None:
    """Submitting the update form with an empty required field shows inline errors."""
    page.goto(demo_base_url + "/admin/user")

    page.get_by_test_id("list-row").first.get_by_test_id("row-edit-link").click()
    expect(page.get_by_test_id("model-form")).to_be_visible()

    page.get_by_label("Name*").fill("")
    page.get_by_role("button", name="Update").click()

    expect(page.get_by_test_id("name-errors")).to_be_visible()
    expect(page.get_by_test_id("model-form")).to_be_visible()


def test_delete_removes_item_from_list(page: Page, demo_base_url: str) -> None:
    """Clicking Delete on a row removes it from the list."""
    page.goto(demo_base_url + "/admin/user")

    rows = page.get_by_test_id("list-row")
    initial_count = rows.count()

    page.on("dialog", lambda d: d.accept())
    rows.last.get_by_test_id("row-delete-btn").click()

    expect(rows).to_have_count(initial_count - 1)


def test_delete_confirm_cancel_keeps_item(page: Page, demo_base_url: str) -> None:
    """Dismissing the delete confirmation leaves the list unchanged."""
    page.goto(demo_base_url + "/admin/user")

    rows = page.get_by_test_id("list-row")
    initial_count = rows.count()

    page.on("dialog", lambda d: d.dismiss())
    rows.last.get_by_test_id("row-delete-btn").click()

    expect(rows).to_have_count(initial_count)
