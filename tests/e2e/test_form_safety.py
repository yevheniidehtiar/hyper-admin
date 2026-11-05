"""E2E: unsaved-changes guard, sticky save bar and Cmd/Ctrl+S (st-v059-kbd-01).

Spec: ``docs/specs/navigation-and-list-ux.md`` ("Form safety (kbd-01)"). One test
per story scenario, against :mod:`tests.e2e.apps.form_safety`: ``Order`` keeps the
guard on (the default), ``Note`` turns it off with
``AdminOptions(warn_unsaved_changes=False)``.

A leave prompt is the browser's ``beforeunload`` dialog. The tests type with the
keyboard, so the page has the user activation browsers require before they show it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Dialog, Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

ORDER_EDIT = "/admin/order/42/edit"


@pytest.fixture
def form_safety_base_url(start_server: Callable[..., str]) -> str:
    """Start :mod:`tests.e2e.apps.form_safety` and return its base URL."""
    return start_server("tests.e2e.apps.form_safety")


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _record_dialogs(page: Page) -> list[str]:
    """Dismiss every dialog (stay on the page) and record its type."""
    seen: list[str] = []

    def handle(dialog: Dialog) -> None:
        seen.append(dialog.type)
        dialog.dismiss()

    page.on("dialog", handle)
    return seen


def _type_into(page: Page, label: str, text: str) -> None:
    field = page.get_by_label(label)
    field.click()
    field.press("End")
    field.press_sequentially(text)


def test_leaving_a_dirty_form_asks_first(page: Page, form_safety_base_url: str) -> None:
    """
    Scenario: leaving a dirty form asks first
      Given the user changed a field on the order edit form
      When  the user clicks a sidebar link
      Then  the browser asks to confirm leaving
    """
    # Given the user changed a field on the order edit form
    _login(page, form_safety_base_url)
    page.goto(form_safety_base_url + ORDER_EDIT)
    _type_into(page, "Customer", " Corp")
    dialogs = _record_dialogs(page)

    # When the user clicks a sidebar link
    with page.expect_event("dialog"):
        page.get_by_test_id("sidebar").get_by_role("link", name="Notes").click()

    # Then the browser asks to confirm leaving (dismissed: the user stays with the edits)
    assert dialogs == ["beforeunload"]
    expect(page).to_have_url(form_safety_base_url + ORDER_EDIT)
    expect(page.get_by_label("Customer")).to_have_value("Acme Corp")


def test_saving_does_not_trigger_the_guard(page: Page, form_safety_base_url: str) -> None:
    """
    Scenario: saving does not trigger the guard
      Given a dirty form
      When  the user clicks Save
      Then  the form submits without a leave prompt
    """
    # Given a dirty form
    _login(page, form_safety_base_url)
    page.goto(form_safety_base_url + ORDER_EDIT)
    _type_into(page, "Customer", " Corp")
    dialogs = _record_dialogs(page)

    # When the user clicks Save
    page.get_by_test_id("form-actions").get_by_role("button", name="Update").click()

    # Then the form submits without a leave prompt
    expect(page).to_have_url(f"{form_safety_base_url}/admin/order")
    expect(page.get_by_test_id("list-row").filter(has_text="ORD-1042")).to_contain_text("Acme Corp")
    assert dialogs == []


def test_cmd_s_saves_the_form(page: Page, form_safety_base_url: str) -> None:
    """
    Scenario: Cmd+S saves the form
      Given the user is on the order edit form
      When  the user presses Cmd+S
      Then  the form is submitted as if Save was clicked
    """
    # Given the user is on the order edit form (with a change to save)
    _login(page, form_safety_base_url)
    page.goto(form_safety_base_url + ORDER_EDIT)
    _type_into(page, "Number", "-B")
    dialogs = _record_dialogs(page)

    # When the user presses Cmd+S (Ctrl+S off macOS)
    page.keyboard.press("ControlOrMeta+s")

    # Then the form is submitted as if Save was clicked
    expect(page).to_have_url(f"{form_safety_base_url}/admin/order")
    expect(page.get_by_test_id("list-row").filter(has_text="ORD-1042-B")).to_be_visible()
    assert dialogs == []


def test_the_guard_can_be_turned_off_per_model(page: Page, form_safety_base_url: str) -> None:
    """
    Scenario: the guard can be turned off per model
      Given AdminOptions(warn_unsaved_changes=False)
      When  the user edits and leaves the form
      Then  no prompt is shown
    """
    # Given AdminOptions(warn_unsaved_changes=False) (the Note admin)
    _login(page, form_safety_base_url)
    page.goto(f"{form_safety_base_url}/admin/note/1/edit")
    dialogs = _record_dialogs(page)

    # When the user edits and leaves the form
    _type_into(page, "Title", " today")
    page.get_by_test_id("sidebar").get_by_role("link", name="Orders").click()

    # Then no prompt is shown
    expect(page).to_have_url(f"{form_safety_base_url}/admin/order")
    assert dialogs == []
