import pytest
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import closing
from http import HTTPStatus
from playwright.sync_api import Page, expect

def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])

@pytest.fixture
def auth_app_url() -> Iterator[str]:
    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.auth_test_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, text=True)
    base = f"http://localhost:{port}"
    try:
        deadline = time.time() + 5
        import requests
        while time.time() < deadline:
            try:
                r = requests.get(base + "/", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception:
                pass
            time.sleep(0.3)
        yield base
    finally:
        proc.terminate()
        proc.wait()

def test_auth_redirect(page: Page, auth_app_url):
    # Go to admin dashboard, should redirect to /admin/login
    page.goto(f"{auth_app_url}/admin/")
    expect(page).to_have_url(f"{auth_app_url}/admin/login")

def test_superuser_access(page: Page, auth_app_url):
    # Log in as admin
    page.goto(f"{auth_app_url}/login/admin")

    # Go to admin dashboard
    page.goto(f"{auth_app_url}/admin/")
    expect(page).to_have_url(f"{auth_app_url}/admin/")
    expect(page.get_by_text("Welcome to HyperAdmin Dashboard")).to_be_visible()
    expect(page.get_by_role("button", name="admin")).to_be_visible() # Username in navbar

def test_restricted_user_forbidden(page: Page, auth_app_url):
    # Log in as restricted user
    page.goto(f"{auth_app_url}/login/restricted")

    # Try to access User list (needs list_user permission)
    page.goto(f"{auth_app_url}/admin/user")

    # We expect a 403.
    expect(page.get_by_text("You do not have permission to list user.")).to_be_visible()

def test_staff_user_access(page: Page, auth_app_url):
    # Log in as staff user
    page.goto(f"{auth_app_url}/login/staff")

    # Access User list (has list_user permission)
    page.goto(f"{auth_app_url}/admin/user")
    expect(page).to_have_url(f"{auth_app_url}/admin/user")

    # Log page content to see what's happening
    print(page.content())

    expect(page.get_by_text("User List")).to_be_visible()

    # Should not see "Create New User" because it doesn't have create_user permission
    expect(page.get_by_role("link", name="Create New User")).not_to_be_visible()

def test_logout(page: Page, auth_app_url):
    # Log in
    page.goto(f"{auth_app_url}/login/admin")
    page.goto(f"{auth_app_url}/admin/")

    # Click logout in navbar
    page.goto(f"{auth_app_url}/admin/logout")

    # Should be redirected to login
    expect(page).to_have_url(f"{auth_app_url}/admin/login")

    # Try to access dashboard again, should be redirected
    page.goto(f"{auth_app_url}/admin/")
    expect(page).to_have_url(f"{auth_app_url}/admin/login")
