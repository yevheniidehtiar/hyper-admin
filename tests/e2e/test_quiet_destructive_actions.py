"""E2E: destructive actions are quiet until needed (st-ux-erp-15), in the full-demo app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def erp_base_url(start_server: Callable[..., str]) -> str:
    """Start the umbrella app (orders with an items inline) and return its base URL."""
    return start_server("tests.e2e.apps.full_demo", extra_env={"E2E_TESTING": "1"})


def _login(page: Page, base: str) -> None:
    page.goto(f"{base}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base}/admin/")


def test_delete_is_quiet_until_needed(page: Page, erp_base_url: str) -> None:
    """
    Scenario: delete is quiet until needed
      Given the order list
      Then  row delete icons are neutral and turn red on hover or focus
      And   inline Remove buttons are neutral and turn red on hover
    """
    # Given the order list
    _login(page, erp_base_url)
    page.goto(f"{erp_base_url}/admin/order")
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

    # And inline Remove buttons are neutral and turn red on hover
    page.goto(f"{erp_base_url}/admin/order/1/edit")
    remove = page.get_by_role("button", name="Remove").first
    quiet = remove.evaluate("el => getComputedStyle(el).color")
    remove.hover()
    assert remove.evaluate("el => getComputedStyle(el).color") != quiet
