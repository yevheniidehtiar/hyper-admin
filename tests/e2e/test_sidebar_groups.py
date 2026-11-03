"""End-to-end tests for the grouped, collapsible sidebar and its icon rail (st-v059-nav-02).

Spec: ``docs/specs/navigation-and-list-ux.md`` — one test per story scenario,
named after it, with ``# Given / # When / # Then`` comments. Selectors follow
``CLAUDE.md``: roles, labels and test ids only, never ``ha-*`` classes.

The companion app is ``tests.e2e.apps.navigation``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def nav_base_url(start_server: Callable[..., str]) -> str:
    """Start the navigation fixture app and return its base URL."""
    return start_server("tests.e2e.apps.navigation")


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_groups_render_with_headings_and_icons(page: Page, nav_base_url: str) -> None:
    """
    Scenario: groups render with headings and icons
      Given models grouped into "Sales" and "Accounting"
      When  an admin opens the dashboard
      Then  the sidebar has headings "Sales" and "Accounting" with their items
    """
    # Given models grouped into "Sales" and "Accounting" (the fixture app)
    # When an admin opens the dashboard
    _login(page, nav_base_url)

    # Then the sidebar has headings "Sales" and "Accounting" with their items
    sales = page.get_by_test_id("nav-group-sales")
    accounting = page.get_by_test_id("nav-group-accounting")
    expect(sales.get_by_role("heading", name="Sales")).to_be_visible()
    expect(accounting.get_by_role("heading", name="Accounting")).to_be_visible()
    expect(sales.get_by_role("link")).to_have_text(["Orders", "Order lines"])
    expect(accounting.get_by_role("link")).to_have_text(["Bills", "Invoices"])
    expect(page.get_by_test_id("nav-order").locator("svg")).to_be_visible()


def test_a_collapsed_group_stays_collapsed_after_reload(page: Page, nav_base_url: str) -> None:
    """
    Scenario: a collapsed group stays collapsed after reload
      Given the "Accounting" group is expanded
      When  the user collapses it and reloads
      Then  the "Accounting" toggle has aria-expanded="false" in the server HTML
    """
    # Given the "Accounting" group is expanded
    _login(page, nav_base_url)
    toggle = page.get_by_role("button", name="Accounting")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_test_id("nav-invoice")).to_be_visible()

    # When the user collapses it and reloads
    toggle.click()
    expect(page.get_by_test_id("nav-invoice")).to_be_hidden()
    response = page.reload()

    # Then the "Accounting" toggle has aria-expanded="false" in the server HTML
    assert response is not None
    assert re.search(r'data-ha-nav-group="accounting"\s+aria-expanded="false"', response.text())
    expect(page.get_by_role("button", name="Accounting")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.get_by_test_id("nav-invoice")).to_be_hidden()
    expect(page.get_by_test_id("nav-order")).to_be_visible()


def test_the_rail_hides_labels_but_keeps_accessible_names(page: Page, nav_base_url: str) -> None:
    """
    Scenario: the rail hides labels but keeps accessible names
      When  the user activates the rail toggle
      Then  nav links keep their accessible names and the rail state survives reload
    """
    _login(page, nav_base_url)
    sidebar = page.get_by_test_id("sidebar")
    expanded_width = sidebar.bounding_box()["width"]  # type: ignore[index]

    # When the user activates the rail toggle
    page.get_by_test_id("sidebar-rail-toggle").click()

    # Then nav links keep their accessible names
    expect(page.get_by_test_id("sidebar-rail-toggle")).to_have_attribute("aria-pressed", "true")
    expect(sidebar.get_by_role("link", name="Orders")).to_be_visible()
    expect(page.get_by_test_id("nav-order")).to_have_attribute("title", "Orders")
    expect(page.get_by_role("heading", name="Sales")).to_be_hidden()
    rail_width = sidebar.bounding_box()["width"]  # type: ignore[index]
    assert rail_width < expanded_width / 2

    # And the rail state survives reload
    page.reload()
    expect(page.get_by_test_id("sidebar-rail-toggle")).to_have_attribute("aria-pressed", "true")
    assert sidebar.bounding_box()["width"] == rail_width  # type: ignore[index]
    expect(sidebar.get_by_role("link", name="Invoices")).to_be_visible()


def test_the_model_of_an_edit_page_is_active(page: Page, nav_base_url: str) -> None:
    """
    Scenario: the model of an edit page is active
      When  the user opens /admin/order/42/edit
      Then  the Orders link has aria-current="page" and Order lines does not
    """
    _login(page, nav_base_url)

    # When the user opens /admin/order/42/edit
    page.goto(f"{nav_base_url}/admin/order/42/edit")

    # Then the Orders link has aria-current="page" and Order lines does not
    expect(page.get_by_test_id("nav-order")).to_have_attribute("aria-current", "page")
    expect(page.get_by_test_id("nav-orderline")).not_to_have_attribute("aria-current", "page")


def test_permission_filtering_removes_empty_groups(page: Page, nav_base_url: str) -> None:
    """
    Scenario: permission filtering removes empty groups
      Given the user may view none of the "Accounting" models
      When  the user opens the dashboard
      Then  no "Accounting" heading is rendered
    """
    # Given the user may view none of the "Accounting" models (bob)
    # When the user opens the dashboard
    _login(page, nav_base_url, "bob")

    # Then no "Accounting" heading is rendered
    sidebar = page.get_by_test_id("sidebar")
    expect(sidebar.get_by_role("heading", name="Sales")).to_be_visible()
    expect(sidebar.get_by_role("heading", name="Accounting")).to_have_count(0)
    expect(page.get_by_test_id("nav-group-accounting")).to_have_count(0)
    expect(page.get_by_test_id("nav-invoice")).to_have_count(0)
