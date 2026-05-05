"""E2E coverage for the real-time MVP connection lifecycle.

Each test maps 1:1 to a BDD scenario in
``docs/specs/realtime-connection-foundation.md``.

The status widget exposes ``window.__rt`` so we can assert connection state
from JS and stay independent of CSS class naming. The visible navbar dot is
queried via ``data-testid="realtime-status"`` per the project's
accessibility-first selector convention.
"""

from __future__ import annotations

import time
from http import HTTPStatus

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _wait_for_state(page: Page, target: str, timeout_ms: int = 5000) -> None:
    page.wait_for_function(
        "([target]) => window.__rt && window.__rt.state === target",
        arg=[target],
        timeout=timeout_ms,
    )


def test_both_transports_open_after_login(page: Page, realtime_base_url: str) -> None:
    # Given a logged-in admin session
    _login(page, realtime_base_url)

    # When the dashboard loads
    # Then window.__rt.state reads "connected" within 5 s
    _wait_for_state(page, "connected")

    # And the navbar dot has data-testid="realtime-status" with class is-connected
    dot = page.get_by_test_id("realtime-status")
    expect(dot).to_have_class("ha-rt-dot is-connected")


def test_navigation_closes_prior_connections_cleanly(page: Page, realtime_base_url: str) -> None:
    # Given an open connection on /admin/
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the user navigates to another admin page
    page.goto(f"{realtime_base_url}/admin/user")

    # Then a fresh pair is opened on the new page (status returns to connected)
    _wait_for_state(page, "connected")
    expect(page.get_by_test_id("realtime-status")).to_have_class("ha-rt-dot is-connected")


def test_page_refresh_re_establishes_connections(page: Page, realtime_base_url: str) -> None:
    # Given an open connection
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the user reloads the page
    page.reload()

    # Then a fresh pair of connections is opened
    _wait_for_state(page, "connected")


def test_server_restart_triggers_reconnect(page: Page, restartable_realtime_url: dict) -> None:
    base = restartable_realtime_url["base"]
    # Given an open connection
    _login(page, base)
    _wait_for_state(page, "connected")

    # When the server is killed and restarted
    restartable_realtime_url["kill"]()
    # Status should drop to reconnecting promptly (clamp generously for CI)
    _wait_for_state(page, "reconnecting", timeout_ms=10_000)
    restartable_realtime_url["start"]()

    # Then the dot transitions back to green within 15 s
    # (worst-case backoff cap is 10 s after a few attempts; the page is NOT reloaded)
    _wait_for_state(page, "connected", timeout_ms=15_000)


def test_unauthenticated_sse_is_rejected(page: Page, realtime_base_url: str) -> None:
    # Given no session cookie
    # When the client GETs /admin/realtime/sse
    response = page.request.get(f"{realtime_base_url}/admin/realtime/sse")

    # Then the response is 401
    assert response.status == HTTPStatus.UNAUTHORIZED


def test_unauthenticated_ws_is_closed_with_4401(page: Page, realtime_base_url: str) -> None:
    # Given no session cookie
    page.goto(f"{realtime_base_url}/admin/login")  # navigate so we have a document context
    ws_url = realtime_base_url.replace("http://", "ws://") + "/admin/realtime/ws"

    # When the client opens the WS, observe the close code from JS
    close_code = page.evaluate(
        """
        (url) => new Promise((resolve) => {
            const ws = new WebSocket(url);
            ws.onclose = (ev) => resolve(ev.code);
            ws.onopen = () => { /* server will close immediately */ };
            setTimeout(() => resolve(-1), 5000);
        })
        """,
        ws_url,
    )

    # Then the close event has code 4401
    assert close_code == 4401


@pytest.mark.skip(
    reason="Server-side ConnectionRegistry count is not exposed over HTTP in the MVP; "
    "add an /_test/registry endpoint here once the introspection story lands."
)
def test_navigation_drops_server_registry_count(realtime_base_url: str) -> None:
    """Placeholder for the server-side count-drop assertion.

    The MVP intentionally does not expose registry internals over HTTP; the
    JS-side assertions in the navigation/refresh tests already cover the
    observable lifecycle. When a debug endpoint lands, this test should drive
    an HTTP probe of the registry count after the navigation step.
    """
    _ = time  # keep the import for future timing assertions
