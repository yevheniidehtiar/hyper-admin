"""E2E: destructive actions are quiet until needed (st-ux-erp-15), in examples/erp."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def erp_base_url(start_server: Callable[..., str]) -> str:
    """Start the ERP showcase and return its base URL."""
    return start_server("examples.erp.main")


def _login(page: Page, base: str) -> None:
    page.goto(f"{base}/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base}/admin/")


def test_delete_is_quiet_until_needed(page: Page, erp_base_url: str) -> None:
    """
    Scenario: delete is quiet until needed
      Given the invoice list
      Then  row delete icons are neutral and turn red on hover or focus
      And   a new invoice form starts with one empty item row
    """
    # Given the invoice list
    _login(page, erp_base_url)
    page.goto(f"{erp_base_url}/admin/invoice")
    delete = page.get_by_test_id("row-delete-btn").first
    muted = delete.evaluate("el => getComputedStyle(el).color")

    # Then row delete icons are neutral and turn red on hover or focus
    delete.hover()
    hovered = delete.evaluate("el => getComputedStyle(el).color")
    assert hovered != muted
    page.mouse.move(0, 0)
    delete.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert delete.evaluate("el => getComputedStyle(el).color") == hovered

    # And a new invoice form starts with one empty item row
    page.goto(f"{erp_base_url}/admin/invoice/create")
    expect(page.get_by_role("button", name="Remove")).to_have_count(1)
