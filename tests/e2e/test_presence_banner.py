"""E2E coverage for the presence banner on the edit page (story #328).

Two browser sessions edit the same record; each sees the other in
``data-testid="presence-banner"`` and the banner goes away when the other
session navigates off the page.
"""

from __future__ import annotations

from playwright.sync_api import Browser, Page, expect


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_banner_hidden_when_editing_alone(page: Page, realtime_base_url: str) -> None:
    # Given alice is the only user on a record
    _login(page, realtime_base_url, "alice")

    # When she opens its edit page
    page.goto(f"{realtime_base_url}/admin/user/1/edit")

    # Then no presence banner is shown
    expect(page.get_by_test_id("presence-banner")).to_be_hidden()


def test_banner_shows_other_editor_and_clears_on_leave(
    browser: Browser, realtime_base_url: str
) -> None:
    # Given alice and bob in separate sessions
    alice_ctx, bob_ctx = browser.new_context(), browser.new_context()
    alice, bob = alice_ctx.new_page(), bob_ctx.new_page()
    try:
        _login(alice, realtime_base_url, "alice")
        _login(bob, realtime_base_url, "bob")

        # When both open the edit page of the same record
        alice.goto(f"{realtime_base_url}/admin/user/1/edit")
        bob.goto(f"{realtime_base_url}/admin/user/1/edit")

        # Then each sees the other in the banner
        expect(alice.get_by_test_id("presence-banner")).to_contain_text("bob")
        expect(bob.get_by_test_id("presence-banner")).to_contain_text("alice")

        # When bob navigates away
        bob.goto(f"{realtime_base_url}/admin/")

        # Then alice's banner disappears
        expect(alice.get_by_test_id("presence-banner")).to_be_hidden()
    finally:
        alice_ctx.close()
        bob_ctx.close()
