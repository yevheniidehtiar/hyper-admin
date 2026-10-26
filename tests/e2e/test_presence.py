"""E2E coverage for presence over two sessions (story #329).

Two admins open the same edit form and see each other in the banner. When one
session goes silent (no leave frame, no more heartbeats) its entry expires
after the configured TTL and the other banner clears on its next heartbeat.
The server runs with ``presence_ttl=2`` so nothing waits for the 30 s default.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Browser, ConsoleMessage, Page, expect

EDIT_PATH = "/admin/user/1/edit"
# Presence heartbeat is 8 s in the browser; allow one full beat plus slack.
CLEAR_TIMEOUT_MS = 20_000


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _record_error(errors: list[str], msg: ConsoleMessage) -> None:
    # Browsers probe /favicon.ico on their own; the app serves none.
    if msg.type == "error" and not msg.location["url"].endswith("favicon.ico"):
        errors.append(f"{msg.text} ({msg.location['url']})")


@contextmanager
def _two_sessions(browser: Browser, base_url: str) -> Iterator[tuple[Page, Page, list[str]]]:
    contexts = [browser.new_context(), browser.new_context()]
    errors: list[str] = []
    try:
        alice, bob = (c.new_page() for c in contexts)
        _login(alice, base_url, "alice")
        _login(bob, base_url, "bob")
        # Watch for errors from the edit forms on (the logged-out login page has no admin prefix
        # for the realtime client, which is outside this scenario).
        for page in (alice, bob):
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda msg: _record_error(errors, msg))
        alice.goto(f"{base_url}{EDIT_PATH}")
        bob.goto(f"{base_url}{EDIT_PATH}")
        yield alice, bob, errors
    finally:
        for c in contexts:
            c.close()


def test_each_editor_sees_the_other_in_banner(
    browser: Browser, realtime_short_ttl_base_url: str
) -> None:
    # Given alice and bob in separate sessions
    with _two_sessions(browser, realtime_short_ttl_base_url) as (alice, bob, errors):
        # When both have the same record's edit form open
        # Then each banner names the other as an editor
        expect(alice.get_by_test_id("presence-banner")).to_contain_text("bob")
        expect(alice.get_by_test_id("presence-banner")).to_contain_text("editing")
        expect(bob.get_by_test_id("presence-banner")).to_contain_text("alice")
        expect(bob.get_by_test_id("presence-banner")).to_contain_text("editing")
        # And neither session logged a console error
        assert errors == []


def test_banner_clears_after_ttl_when_other_session_goes_silent(
    browser: Browser, realtime_short_ttl_base_url: str
) -> None:
    # Given alice and bob both see each other
    with _two_sessions(browser, realtime_short_ttl_base_url) as (alice, bob, errors):
        expect(alice.get_by_test_id("presence-banner")).to_contain_text("bob")

        # When bob's tab stops sending anything (crash: no leave, no heartbeats)
        bob.evaluate("WebSocket.prototype.send = function () {}")

        # Then bob's entry expires after the 2 s TTL and alice's banner clears
        expect(alice.get_by_test_id("presence-banner")).to_be_hidden(timeout=CLEAR_TIMEOUT_MS)
        assert errors == []
