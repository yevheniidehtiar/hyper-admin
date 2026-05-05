"""E2E coverage for the real-time MVP connection lifecycle.

Each test maps 1:1 to a BDD scenario in
``docs/specs/realtime-connection-foundation.md``.

The status widget exposes ``window.__rt`` so we can assert connection state
from JS and stay independent of CSS class naming. The visible navbar dot is
queried via ``data-testid="realtime-status"`` per the project's
accessibility-first selector convention.
"""

from __future__ import annotations

from http import HTTPStatus

from playwright.sync_api import BrowserContext, Page, expect


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


def _registry_count(page: Page, base_url: str) -> dict:
    """Read the server-side registry snapshot via the test-only debug endpoint."""
    response = page.request.get(f"{base_url}/admin/_test/realtime/count")
    assert response.status == HTTPStatus.OK, response.text()
    return response.json()


def _wait_until(predicate, timeout_ms: int = 5000, interval_ms: int = 100) -> bool:
    """Poll ``predicate`` until True or timeout. Returns the final result."""
    import time as _t

    deadline = _t.monotonic() + timeout_ms / 1000.0
    while _t.monotonic() < deadline:
        if predicate():
            return True
        _t.sleep(interval_ms / 1000.0)
    return predicate()


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


def test_navigation_drops_server_registry_count(page: Page, realtime_base_url: str) -> None:
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")
    initial = _registry_count(page, realtime_base_url)
    assert initial["count"] >= 2  # 1 SSE + 1 WS for alice
    assert initial["users"] == [initial["users"][0]]  # only alice connected

    # When the user navigates to another admin page
    page.goto(f"{realtime_base_url}/admin/user")
    _wait_for_state(page, "connected")

    # Then the server-side count returns to the same baseline (old pair gone, new pair registered)
    assert _wait_until(
        lambda: _registry_count(page, realtime_base_url)["count"] == initial["count"],
        timeout_ms=5_000,
    ), (
        f"registry count did not return to baseline; latest={_registry_count(page, realtime_base_url)}"
    )


def test_heartbeat_keeps_idle_connection_alive(page: Page, realtime_base_url: str) -> None:
    # Given a logged-in admin session
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")
    # Capture the reconnect-attempt counter on each transport (0 means no reconnect happened)
    attempts_before = page.evaluate(
        "() => ({ sse: window.__rt.sse.attempt, ws: window.__rt.ws.attempt })"
    )
    assert attempts_before == {"sse": 0, "ws": 0}

    # When the page sits idle for ~3× heartbeat_interval (3 s with the test app's 1 s setting)
    page.wait_for_timeout(3500)

    # Then the connection is still green and no reconnect was attempted
    expect(page.get_by_test_id("realtime-status")).to_have_class("ha-rt-dot is-connected")
    attempts_after = page.evaluate(
        "() => ({ sse: window.__rt.sse.attempt, ws: window.__rt.ws.attempt })"
    )
    assert attempts_after == {"sse": 0, "ws": 0}, (
        f"unexpected reconnect during idle period: {attempts_after}"
    )


def test_drop_then_offline_then_online_heals(
    page: Page, context: BrowserContext, realtime_base_url: str
) -> None:
    """Simulate the realistic Wi-Fi-blip sequence.

    Chromium's ``set_offline(True)`` only blocks *new* connections; existing
    sockets stay alive until the server side closes them. To reproduce a true
    network outage we (1) server-disconnect the live sockets, (2) take the
    browser offline so reconnect attempts fail, (3) bring it back online and
    expect a clean heal.
    """
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the underlying sockets drop and the browser is offline (reconnect attempts fail)
    page.request.post(f"{realtime_base_url}/admin/_test/realtime/disconnect_all")
    context.set_offline(True)
    _wait_for_state(page, "reconnecting", timeout_ms=10_000)

    # And then connectivity returns
    context.set_offline(False)

    # Then the dot heals back to green within 15 s without a page reload
    _wait_for_state(page, "connected", timeout_ms=15_000)


def test_server_disconnects_all_then_client_reconnects(page: Page, realtime_base_url: str) -> None:
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the server force-closes every live connection (no process restart)
    response = page.request.post(f"{realtime_base_url}/admin/_test/realtime/disconnect_all")
    assert response.status == HTTPStatus.OK
    body = response.json()
    assert body["closed"] >= 2

    # Then the client notices the drop and heals back to connected
    _wait_for_state(page, "reconnecting", timeout_ms=5_000)
    _wait_for_state(page, "connected", timeout_ms=15_000)


def test_only_ws_drop_recovers_without_reload(page: Page, realtime_base_url: str) -> None:
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When only the WebSocket transport is dropped server-side
    response = page.request.post(f"{realtime_base_url}/admin/_test/realtime/disconnect/ws")
    assert response.status == HTTPStatus.OK
    assert response.json()["closed"] >= 1

    # Then the dot transitions to reconnecting (one transport down) and back to connected.
    # The state machine only emits "reconnecting" when at least one channel handle is
    # missing-or-dropped — so observing this transition proves the WS specifically
    # dropped and was re-established (the SSE was not touched by the disconnect call).
    _wait_for_state(page, "reconnecting", timeout_ms=5_000)
    _wait_for_state(page, "connected", timeout_ms=15_000)


def test_repeated_failures_increase_reconnect_attempts(
    page: Page, context: BrowserContext, realtime_base_url: str
) -> None:
    """Backoff actually backs off — repeated reconnect attempts recorded."""
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the live sockets drop and the browser stays offline long enough for several backoff cycles
    page.request.post(f"{realtime_base_url}/admin/_test/realtime/disconnect_all")
    context.set_offline(True)
    _wait_for_state(page, "reconnecting", timeout_ms=10_000)
    page.wait_for_timeout(4_000)  # 250 + 500 + 1000 + 2000 ≈ 4 attempts within 4 s
    attempts_during_outage = page.evaluate(
        "() => ({ sse: window.__rt.sse.attempt, ws: window.__rt.ws.attempt })"
    )
    # And then connectivity returns
    context.set_offline(False)
    _wait_for_state(page, "connected", timeout_ms=15_000)

    # Then both transports recorded multiple reconnect attempts (proves backoff drives retry)
    assert attempts_during_outage["sse"] >= 2, attempts_during_outage
    assert attempts_during_outage["ws"] >= 2, attempts_during_outage


def test_long_disconnect_heals_after_backoff_cap(
    page: Page, context: BrowserContext, realtime_base_url: str
) -> None:
    """Heal still works after the backoff has grown to the 10 s cap."""
    # Given a logged-in admin session with both transports connected
    _login(page, realtime_base_url)
    _wait_for_state(page, "connected")

    # When the live sockets drop and the browser stays offline long enough for backoff to reach cap
    # 250 ms × 2ⁿ caps at 10 s after attempt 6; wait 12 s to ensure the cap is exercised.
    page.request.post(f"{realtime_base_url}/admin/_test/realtime/disconnect_all")
    context.set_offline(True)
    _wait_for_state(page, "reconnecting", timeout_ms=10_000)
    page.wait_for_timeout(12_000)

    # And then connectivity returns
    context.set_offline(False)

    # Then the dot heals back to green within one capped backoff window (≤ 15 s slack)
    _wait_for_state(page, "connected", timeout_ms=15_000)
