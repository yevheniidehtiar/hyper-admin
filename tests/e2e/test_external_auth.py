"""E2E tests for the bring-your-own-app example, ``examples/byoa`` (st-v058-byoa-51).

The host owns its login page, its JWT and its user model; HyperAdmin is wired
with ``Admin(auth=ExternalAuth(get_user=..., login_url="/login",
token_cookie=TokenCookie()))``. One test per scenario.

The server fixture lives here, not in ``conftest.py`` (a hotspot file): it starts
``examples.byoa.main:app`` with uvicorn, sends its output to a temp log file
(never an unread pipe) and waits up to the usual start timeout for ``/health``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from playwright.sync_api import Page, expect

# Same budget as the conftest servers: slower inside a container.
_SERVER_TIMEOUT = 30 if os.environ.get("IS_SANDBOX") == "1" else 15


@pytest.fixture
def byoa_base_url(e2e_port: int) -> Iterator[str]:
    """Start ``examples/byoa`` (fresh in-memory database) and yield its base URL."""
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.byoa.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(e2e_port),
        "--log-level",
        "warning",
    ]
    env = os.environ.copy()
    env["E2E_TESTING"] = "1"
    env.pop("BYOA_DATABASE_URL", None)
    env["HYPERADMIN_SECRET_KEY"] = "byoa-e2e-admin-secret"
    with tempfile.TemporaryFile(mode="w+") as server_log:
        proc = subprocess.Popen(cmd, stdout=server_log, stderr=subprocess.STDOUT, env=env)
        base = f"http://localhost:{e2e_port}"
        try:
            deadline = time.time() + _SERVER_TIMEOUT
            last_err: Exception | None = None
            while time.time() < deadline:
                try:
                    if requests.get(f"{base}/health", timeout=0.5).status_code == HTTPStatus.OK:
                        break
                except Exception as exc:
                    last_err = exc
                time.sleep(0.3)
            else:
                server_log.seek(0)
                raise RuntimeError(f"Server did not start: {last_err}\n{server_log.read()[-4000:]}")
            yield base
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


def _sign_in(
    page: Page,
    username: str = "ada",
    password: str = "lovelace",  # noqa: S107 - the example's demo credentials
) -> None:
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def test_e2e_login_round_trip(page: Page, byoa_base_url: str) -> None:
    """
    Scenario: e2e login round-trip
      Given the byoa example with login_url='/login'
      When  an anonymous browser opens /admin/
      Then  it lands on /login and returns to /admin/ after login
    """
    # Given the byoa example with login_url='/login' (a fresh browser context)
    # When an anonymous browser opens /admin/
    page.goto(f"{byoa_base_url}/admin/")

    # Then it lands on /login
    expect(page).to_have_url(f"{byoa_base_url}/login?next=%2Fadmin%2F")
    # And returns to /admin/ after login
    _sign_in(page)
    expect(page).to_have_url(f"{byoa_base_url}/admin/")
    expect(page.get_by_test_id("current-user")).to_have_text("ada")


def test_e2e_htmx_delete_in_bridge_mode(page: Page, byoa_base_url: str) -> None:
    """
    Scenario: e2e HTMX delete in bridge mode
      Given a token cookie from the handoff
      When  the user deletes a row
      Then  the row disappears
    """
    # Given a token cookie from the handoff
    page.goto(f"{byoa_base_url}/login?next=%2Fadmin%2Fproject")
    _sign_in(page)
    expect(page).to_have_url(f"{byoa_base_url}/admin/project")
    assert [c for c in page.context.cookies() if c["name"] == "hyperadmin_token"]
    row = page.get_by_test_id("list-row").filter(has_text="Compiler")
    expect(row).to_have_count(1)

    # When the user deletes a row
    page.on("dialog", lambda dialog: dialog.accept())
    with page.expect_response(lambda r: r.request.method == "DELETE") as response_info:
        row.get_by_test_id("row-delete-btn").click()

    # Then the row disappears
    assert response_info.value.status == HTTPStatus.OK
    expect(row).to_have_count(0)
    expect(page.get_by_test_id("list-row").filter(has_text="Analytical Engine")).to_have_count(1)
