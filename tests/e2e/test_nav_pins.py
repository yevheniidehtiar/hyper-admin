"""End-to-end tests for per-user pinned pages in the sidebar (st-v059-nav-03).

Spec: ``docs/specs/navigation-and-list-ux.md`` — one test per story scenario,
named after it, with ``# Given / # When / # Then`` comments. Selectors follow
``CLAUDE.md``: roles, labels and test ids only, never ``ha-*`` classes.

The companion app is ``tests.e2e.apps.navigation`` (alice, bob and carol);
the no-auth scenario uses the demo app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Browser, Page, expect

from tests.e2e.conftest import csrf_headers

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


def _pin_orders(page: Page) -> None:
    page.get_by_test_id("nav-order").hover()
    with page.expect_response(lambda r: r.url.endswith("/admin/nav/pins")) as pinned:
        page.get_by_test_id("nav-pin-order").click()
    assert pinned.value.status == 200
    expect(page.get_by_test_id("nav-pin-order")).to_have_attribute("aria-pressed", "true")


def test_pinning_a_model_adds_it_to_the_pinned_group(page: Page, nav_base_url: str) -> None:
    """
    Scenario: pinning a model adds it to the Pinned group
      Given alice is signed in with no pins
      When  alice pins Orders
      Then  the Pinned group shows Orders and the toggle has aria-pressed="true"
    """
    # Given alice is signed in with no pins
    _login(page, nav_base_url)
    expect(page.get_by_test_id("nav-pinned")).to_have_count(0)

    # When alice pins Orders
    page.get_by_test_id("nav-order").hover()
    page.get_by_role("button", name="Pin Orders").click()

    # Then the Pinned group shows Orders and the toggle has aria-pressed="true"
    pinned = page.get_by_test_id("nav-pinned")
    expect(pinned.get_by_role("heading", name="Pinned")).to_be_visible()
    expect(pinned.get_by_role("link", name="Orders")).to_be_visible()
    toggle = page.get_by_test_id("nav-pin-order")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(toggle).to_have_accessible_name("Unpin Orders")
    expect(toggle).to_be_focused()


def test_pins_follow_the_user_to_another_browser(
    page: Page, browser: Browser, nav_base_url: str
) -> None:
    """
    Scenario: pins follow the user to another browser
      Given alice pinned Orders
      When  alice signs in from a new browser context
      Then  Orders is in her Pinned group
    """
    # Given alice pinned Orders
    _login(page, nav_base_url)
    _pin_orders(page)

    # When alice signs in from a new browser context
    context = browser.new_context()
    try:
        other = context.new_page()
        _login(other, nav_base_url)

        # Then Orders is in her Pinned group
        expect(
            other.get_by_test_id("nav-pinned").get_by_role("link", name="Orders")
        ).to_be_visible()
    finally:
        context.close()


def test_pins_are_per_user(page: Page, browser: Browser, nav_base_url: str) -> None:
    """
    Scenario: pins are per user
      Given alice pinned Orders
      When  bob opens the dashboard
      Then  bob has no Pinned group
    """
    # Given alice pinned Orders
    _login(page, nav_base_url)
    _pin_orders(page)

    # When bob opens the dashboard
    context = browser.new_context()
    try:
        bob = context.new_page()
        _login(bob, nav_base_url, "bob")

        # Then bob has no Pinned group
        expect(bob.get_by_test_id("nav-order")).to_be_visible()
        expect(bob.get_by_test_id("nav-pinned")).to_have_count(0)
        expect(bob.get_by_test_id("nav-pin-order")).to_have_attribute("aria-pressed", "false")
    finally:
        context.close()


def test_a_pinned_page_is_listed_under_pinned_in_the_palette(page: Page, nav_base_url: str) -> None:
    """
    Scenario: a pinned page is listed under Pinned in the palette
      Given carol pinned Orders (and Invoices, which she may no longer view)
      When  carol opens the palette with an empty query
      Then  the Pinned section lists Orders and not Invoices
    """
    # Given carol pinned Orders (and Invoices, which she may no longer view)
    _login(page, nav_base_url, "carol")

    # When carol opens the palette with an empty query
    page.keyboard.press("ControlOrMeta+k")
    expect(page.get_by_test_id("command-palette")).to_be_visible()

    # Then the Pinned section lists Orders and not Invoices
    pinned = page.get_by_role("group", name="Pinned")
    expect(pinned.get_by_test_id("palette-result")).to_have_count(1)
    expect(pinned.get_by_test_id("palette-result").filter(has_text="Orders")).to_be_visible()


def test_a_pin_the_user_can_no_longer_view_is_hidden(page: Page, nav_base_url: str) -> None:
    """
    Scenario: a pin the user can no longer view is hidden
      Given alice pinned Invoices and then loses view_invoice
      When  alice opens the dashboard
      Then  Invoices is not shown in Pinned
    """
    # Given a user who pinned Invoices and Orders and then lost view_invoice (carol)
    # When she opens the dashboard
    _login(page, nav_base_url, "carol")

    # Then Invoices is not shown in Pinned
    pinned = page.get_by_test_id("nav-pinned")
    expect(pinned.get_by_role("link")).to_have_text(["Orders"])
    expect(page.get_by_test_id("sidebar").get_by_role("link", name="Invoices")).to_have_count(0)


def test_unknown_or_forbidden_pin_targets_return_404(page: Page, nav_base_url: str) -> None:
    """
    Scenario: unknown or forbidden pin targets return 404
      When  alice POSTs target="secretmodel"
      Then  the response is 404
    """
    _login(page, nav_base_url, "bob")
    url = f"{nav_base_url}/admin/nav/pins"

    # When the user POSTs target="secretmodel", and a model they may not view
    unknown = page.request.post(url, form={"target": "secretmodel"}, headers=csrf_headers(page))
    forbidden = page.request.post(url, form={"target": "invoice"}, headers=csrf_headers(page))

    # Then the response is 404
    assert unknown.status == 404
    assert forbidden.status == 404


def test_a_pin_beyond_the_limit_is_refused(page: Page, start_server: Callable[..., str]) -> None:
    """
    Scenario: a pin beyond the limit is refused
      Given nav_pins_max is 20 (default) and alice has 20 pins
      When  alice pins another page
      Then  the response is 409 and an error toast explains the limit
    """
    # Given nav_pins_max is 2 (HYPERADMIN_NAV_PINS_MAX) and alice has 2 pins
    # (the limit of 20 itself is covered by tests/unit/test_nav_pins.py)
    base_url = start_server("tests.e2e.apps.navigation", extra_env={"HYPERADMIN_NAV_PINS_MAX": "2"})
    _login(page, base_url)
    for key in ("order", "orderline"):
        page.get_by_test_id(f"nav-{key}").hover()
        page.get_by_test_id(f"nav-pin-{key}").click()
        expect(page.get_by_test_id(f"nav-pin-{key}")).to_have_attribute("aria-pressed", "true")

    # When alice pins another page
    page.get_by_test_id("nav-invoice").hover()
    with page.expect_response(f"{base_url}/admin/nav/pins") as refused:
        page.get_by_test_id("nav-pin-invoice").click()

    # Then the response is 409 and an error toast explains the limit
    assert refused.value.status == 409
    expect(page.get_by_test_id("error-toast")).to_contain_text("You can pin up to 2 pages")
    expect(page.get_by_test_id("nav-pin-invoice")).to_have_attribute("aria-pressed", "false")
    expect(page.get_by_test_id("nav-pinned").get_by_role("link")).to_have_count(2)


def test_no_auth_means_no_pins(page: Page, demo_base_url: str) -> None:
    """
    Scenario: no auth means no pins
      Given HyperAdmin without auth
      When  the dashboard renders
      Then  no pin toggles are rendered and /nav/pins is not routed
    """
    # Given HyperAdmin without auth (the demo app)
    # When the dashboard renders
    page.goto(f"{demo_base_url}/admin/")

    # Then no pin toggles are rendered and /nav/pins is not routed
    expect(page.get_by_test_id("nav-user")).to_be_visible()
    expect(page.get_by_test_id("nav-pin-user")).to_have_count(0)
    expect(page.get_by_test_id("nav-pinned")).to_have_count(0)
    response = page.request.post(f"{demo_base_url}/admin/nav/pins", form={"target": "user"})
    assert response.status == 404


def test_pins_appear_on_demand(page: Page, nav_base_url: str) -> None:
    """
    Scenario: pins appear on demand
      Given the sidebar
      Then  a pin button is visible only on the hovered or focused item and on already-pinned items
    """
    # Given alice is signed in and has pinned Orders
    _login(page, nav_base_url)
    _pin_orders(page)
    page.mouse.move(700, 600)

    # Then a pin on an untouched, unpinned item is hidden
    idle = page.get_by_test_id("nav-pin-invoice")
    expect(idle).to_have_css("opacity", "0")

    # And the pin on the already-pinned item stays visible
    expect(page.get_by_test_id("nav-pin-order")).to_have_css("opacity", "1")

    # And hovering an item reveals its pin
    page.get_by_test_id("nav-invoice").hover()
    expect(idle).to_have_css("opacity", "1")

    # And keyboard focus reveals it too
    page.mouse.move(700, 600)
    page.get_by_test_id("nav-invoice").focus()
    expect(idle).to_have_css("opacity", "1")
