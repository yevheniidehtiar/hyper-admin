"""E2E tests for file upload functionality (#398).

Verifies that file upload fields render correctly, files can be uploaded
via the create form, and uploaded filenames appear on the detail view.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_IN_CONTAINER = os.environ.get("IS_SANDBOX") == "1"
_SERVER_TIMEOUT = 15 if _IN_CONTAINER else 5


@pytest.fixture
def upload_base_url(e2e_port: int) -> Iterator[str]:
    """Start the upload test app via uvicorn and yield the base URL."""
    pytest.importorskip("uvicorn")
    requests = pytest.importorskip("requests")  # type: ignore[assignment]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tests.e2e._upload_app:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(e2e_port),
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

    base = f"http://localhost:{e2e_port}"

    try:
        deadline = time.time() + _SERVER_TIMEOUT
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
            raise RuntimeError(f"Upload server did not start: {last_err}")

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


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a small text file for upload tests."""
    f = tmp_path / "test_upload.txt"
    f.write_text("hello world")
    return f


def test_file_input_renders_for_file_field(
    page: Page,
    upload_base_url: str,
) -> None:
    """Scenario: file input renders for FileType column.

    Given a Document model with a FileType ``attachment`` field
    When  the user navigates to the create form
    Then  the form contains a file input for the attachment field
    """
    # Given a Document model registered with a FileType attachment field
    # (provided by the upload_app fixture)

    # When the user navigates to the create form
    page.goto(f"{upload_base_url}/admin/document/create")

    # Then the form contains a file input for the attachment field
    form = page.get_by_test_id("model-form")
    expect(form).to_be_visible()

    attachment_input = page.get_by_test_id("attachment-file-input")
    expect(attachment_input).to_be_visible()
    expect(attachment_input).to_have_attribute("type", "file")

    # And the cover_image field also has a file input
    cover_input = page.get_by_test_id("cover_image-file-input")
    expect(cover_input).to_be_visible()
    expect(cover_input).to_have_attribute("type", "file")


def test_create_record_with_file_upload(
    page: Page,
    upload_base_url: str,
    sample_file: Path,
) -> None:
    """Scenario: create a record with a file attachment.

    Given a Document model with a FileType ``attachment`` field
    When  the user fills the title and attaches a file, then submits
    Then  the record is created and the detail view is shown
    """
    # Given the create form is loaded
    page.goto(f"{upload_base_url}/admin/document/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    # When the user fills the title field
    page.get_by_label("Title").fill("My Document")

    # And attaches a file to the attachment field
    page.get_by_test_id("attachment-file-input").set_input_files(str(sample_file))

    # And submits the form
    page.get_by_role("button", name="Create").click()

    # Then the record is created and the detail view is shown
    expect(page).to_have_url(re.compile(r"/admin/document/\d+$"))
    detail = page.get_by_test_id("detail-fields")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("My Document")


def test_detail_view_shows_filename(
    page: Page,
    upload_base_url: str,
    sample_file: Path,
) -> None:
    """Scenario: detail view shows uploaded filename.

    Given a Document record was created with file ``test_upload.txt``
    When  the user views the detail page for that record
    Then  the filename ``test_upload.txt`` is visible on the page
    """
    # Given a Document record is created with an attached file
    page.goto(f"{upload_base_url}/admin/document/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()

    page.get_by_label("Title").fill("File Detail Test")
    page.get_by_test_id("attachment-file-input").set_input_files(str(sample_file))
    page.get_by_role("button", name="Create").click()

    # When the detail page is shown after creation
    expect(page).to_have_url(re.compile(r"/admin/document/\d+$"))

    # Then the filename is visible in the detail view
    detail = page.get_by_test_id("detail-fields")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("test_upload.txt")

    # And the filename is rendered as a download link
    download_link = page.get_by_test_id("attachment-download")
    expect(download_link).to_be_visible()
    expect(download_link).to_contain_text("test_upload.txt")
