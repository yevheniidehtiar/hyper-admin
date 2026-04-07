"""E2E tests for the ERP Profit & Loss report page."""

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from http import HTTPStatus
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


_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"
# ERP app performs DB creation + permission sync + data seeding on startup,
# which takes longer than the simple demo app.
_SERVER_TIMEOUT = 30 if _IN_CONTAINER else 15


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


@pytest.fixture
def erp_base_url() -> Iterator[str]:
    """Start the ERP demo app via uvicorn in a subprocess and yield base URL."""
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    port = _find_free_port()

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.erp.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]

    env = os.environ.copy()
    env["E2E_TESTING"] = "1"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    base = f"http://localhost:{port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
        last_err: Exception | None = None
        while time.time() < deadline:
            # If the subprocess already exited, report its stderr immediately
            if proc.poll() is not None:
                _stdout, _stderr = proc.communicate()
                raise RuntimeError(
                    f"ERP server process exited with code {proc.returncode}:\n{_stderr}"
                )
            try:
                r = requests.get(base + "/", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"ERP server did not start within {_SERVER_TIMEOUT}s: {last_err}")

        yield base
    finally:
        if proc.poll() is None:
            try:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


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
