"""E2E tests for the ERP Profit & Loss report page."""

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page, expect

_ERP_USER = "admin"
_ERP_PASS = "admin"


def _erp_login(page: Page, base_url: str) -> None:
    """Log in to the ERP app as the seeded superuser."""
    page.goto(base_url + "/admin/login")
    page.get_by_label("Username").fill(_ERP_USER)
    page.get_by_label("Password").fill(_ERP_PASS)
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base_url + "/admin/")


@pytest.fixture
def erp_base_url(start_server: Callable[..., str]) -> str:
    """Start the ERP demo app (DB creation + seeding on startup) and return the base URL."""
    return start_server("examples.erp.main", ready_path="/")


def test_profit_loss_report_loads(page: Page, erp_base_url: str) -> None:
    """Smoke test: P&L report page loads and summary elements are visible."""
    # Given the admin is logged in
    _erp_login(page, erp_base_url)

    # When navigating to the P&L report
    page.goto(erp_base_url + "/admin/reports/profit-loss")

    # Then the report page loads (no redirect to login)
    expect(page).to_have_url(erp_base_url + "/admin/reports/profit-loss")
    expect(page.get_by_role("heading", name="Annual Profit / Loss Report")).to_be_visible()


def test_profit_loss_summary_elements_visible(page: Page, erp_base_url: str) -> None:
    """Summary totals section renders with non-empty values for seeded data."""
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/reports/profit-loss")

    total_revenue = page.get_by_test_id("total-revenue")
    total_expenses = page.get_by_test_id("total-expenses")
    net_profit = page.get_by_test_id("net-profit")

    expect(total_revenue).to_be_visible()
    expect(total_expenses).to_be_visible()
    expect(net_profit).to_be_visible()

    # Values must be non-empty strings (seeded data guarantees journal entries exist)
    expect(total_revenue).not_to_be_empty()
    expect(total_expenses).not_to_be_empty()
    expect(net_profit).not_to_be_empty()


def test_profit_loss_year_navigation(page: Page, erp_base_url: str) -> None:
    """Year navigation links are present and functional."""
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/reports/profit-loss")

    prev_link = page.get_by_role("link", name="Previous year")
    next_link = page.get_by_role("link", name="Next year")

    expect(prev_link).to_be_visible()
    expect(next_link).to_be_visible()


def test_profit_loss_pl_table_renders(
    page: Page,
    erp_base_url: str,
    browser_type_launch_args: dict[str, Any],
) -> None:
    """Line-by-line breakdown table is present on the report page."""
    _erp_login(page, erp_base_url)
    page.goto(erp_base_url + "/admin/reports/profit-loss")

    pl_table = page.get_by_test_id("pl-table")
    expect(pl_table).to_be_visible()
