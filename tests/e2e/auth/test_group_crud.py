import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from http import HTTPStatus

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.e2e.conftest import _find_free_port


@pytest.fixture
def rbac_base_url() -> Iterator[str]:
    """Start the rbac_app via uvicorn in a subprocess and yield base URL."""
    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "examples.rbac_app.main:app",
        "--host",
        "127.0.0.1",
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
        # Wait for server readiness
        deadline = time.time() + 10
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                r = requests.get(base + "/", timeout=0.5)
                if r.status_code == HTTPStatus.OK:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        else:
            raise RuntimeError(f"Server did not start: {last_err}")

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


def test_group_list_renders(page: Page, rbac_base_url):
    """Verify group list page renders at /admin/group with expected elements."""
    page.goto(f"{rbac_base_url}/admin/group")

    expect(page).to_have_url(f"{rbac_base_url}/admin/group")
    # Verify table is present with data-testid="list-table"
    expect(page.locator('[data-testid="list-table"]')).to_be_visible()

    # Verify column headers (based on column_list in GroupAdmin)
    expect(page.get_by_role("columnheader", name="Id")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Name")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Description")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Is active")).to_be_visible()
    expect(page.get_by_role("columnheader", name="Created at")).to_be_visible()


def test_create_group_form_accessible(page: Page, rbac_base_url):
    """Verify create group form accessible; fields via page.get_by_label("Name"), etc."""
    page.goto(f"{rbac_base_url}/admin/group/create")

    # Verify form fields are present via labels
    expect(page.get_by_label("Name")).to_be_visible()
    expect(page.get_by_label("Description")).to_be_visible()
    expect(page.get_by_label("Is active")).to_be_visible()


def test_sidebar_links(page: Page, rbac_base_url):
    """Sidebar shows 'Groups' and 'Permissions' links."""
    page.goto(f"{rbac_base_url}/admin/")

    # Check for "Groups" and "Permissions" in the sidebar
    expect(page.get_by_role("link", name="Groups", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Permissions", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="User Groups")).to_be_visible()
    expect(page.get_by_role("link", name="User Permissions")).to_be_visible()
