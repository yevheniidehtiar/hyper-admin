"""E2E smoke for realtime wiring in the full-demo app (story #784).

Spec: ``docs/specs/realtime-demo-apps.md`` (E2E smoke). Boots ``tests.e2e.apps.full_demo``
(``examples/full-demo/main.py``) with two browser contexts, ``alice`` and ``bob``
(superusers, password ``secret123``). The other full-demo scenarios are library behaviour
covered by ``test_realtime_notifications.py`` and are checked by hand from the README.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from playwright.sync_api import Browser, BrowserContext, ConsoleMessage, Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

ORDERS = "/admin/order"
SUPPLIERS = "/admin/supplier"
# Debounce (300 ms) + request + swap, with slack for a loaded CI box.
LIVE_MS = 8_000
# How long to watch for something that must NOT happen.
QUIET_MS = 1_500


@pytest.fixture
def demo_url(start_server: Callable[..., str]) -> str:
    """The full-demo app with realtime on (the default) and test endpoints enabled."""
    return start_server("tests.e2e.apps.full_demo", extra_env={"E2E_TESTING": "1"})


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _record_error(errors: list[str], msg: ConsoleMessage) -> None:
    if msg.type != "error" or msg.location["url"].endswith("favicon.ico"):
        return
    errors.append(f"{msg.text} ({msg.location['url']})")


@contextmanager
def _sessions(
    browser: Browser, base_url: str, *usernames: str
) -> Iterator[tuple[list[BrowserContext], list[str]]]:
    """One signed-in browser context per user, sharing one list of console errors."""
    contexts = [browser.new_context() for _ in usernames]
    errors: list[str] = []

    def attach(page: Page) -> None:
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: _record_error(errors, msg))

    try:
        for context, username in zip(contexts, usernames, strict=True):
            context.on("page", attach)
            _login(context.new_page(), base_url, username)
        yield contexts, errors
    finally:
        for context in contexts:
            context.close()


def _open_list(context: BrowserContext, base_url: str, path: str) -> Page:
    page = context.new_page()
    page.goto(f"{base_url}{path}")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    return page


def _row(page: Page, pk: int) -> Any:
    return page.get_by_test_id("list-row").and_(page.locator(f'[data-pk="{pk}"]'))


def test_full_demo_order_list_updates_live_for_another_user(
    browser: Browser, demo_url: str
) -> None:
    """
    Scenario: full-demo order list updates live for another user
      Given full-demo is running and alice and bob are signed in, both on the Orders list
      When  alice edits order ORD-2 and saves
      Then  bob's Orders list re-fetches without a reload
      And   the ORD-2 row is highlighted in bob's browser
    """
    # Given alice and bob are both on the Orders list
    with _sessions(browser, demo_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, demo_url, ORDERS)
        expect(bob_list.get_by_test_id("realtime-hook")).to_have_count(1)
        expect(_row(bob_list, 2)).to_contain_text("shipped")
        bob_list.evaluate("window.__noReload = true")

        # When alice edits ORD-2 and saves
        form = alice.new_page()
        form.goto(f"{demo_url}{ORDERS}/2/edit")
        form.get_by_label("Status", exact=True).fill("delivered")
        form.get_by_role("button", name="Update").click()

        # Then bob's list shows the new status without a reload
        row = _row(bob_list, 2)
        expect(row).to_contain_text("delivered", timeout=LIVE_MS)
        assert bob_list.evaluate("window.__noReload") is True
        # And the ORD-2 row is highlighted
        expect(row).to_have_attribute("data-realtime-flash", "true")
        assert errors == []


def test_full_demo_model_without_opt_in_stays_static(browser: Browser, demo_url: str) -> None:
    """
    Scenario: full-demo model without opt-in stays static
      Given alice and bob are both on the Suppliers list
      When  alice edits a supplier
      Then  bob's Suppliers list does not change until he reloads
    """
    # Given alice and bob are both on the Suppliers list
    with _sessions(browser, demo_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, demo_url, SUPPLIERS)
        expect(_row(bob_list, 42)).to_contain_text("Acme")
        # And the list does not subscribe to live updates at all
        expect(bob_list.get_by_test_id("realtime-hook")).to_have_count(0)

        # When alice renames supplier 42
        form = alice.new_page()
        form.goto(f"{demo_url}{SUPPLIERS}/42/edit")
        form.get_by_label("Name", exact=True).fill("Acme Renamed")
        form.get_by_role("button", name="Update").click()
        expect(form).to_have_url(f"{demo_url}{SUPPLIERS}/42")

        # Then bob's list is unchanged after a quiet period
        bob_list.wait_for_timeout(QUIET_MS)
        expect(_row(bob_list, 42)).not_to_contain_text("Renamed")
        # And a reload shows the change
        bob_list.reload()
        expect(_row(bob_list, 42)).to_contain_text("Acme Renamed")
        assert errors == []
