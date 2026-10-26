"""E2E tests for the image preview widget: drag-and-drop zone and keyboard access (#403, #405)."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# 1x1 transparent PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

_DROP_JS = """
(el, {name, type, count}) => {
  const dt = new DataTransfer();
  for (let i = 0; i < count; i++) {
    dt.items.add(new File([new Uint8Array([1, 2, 3])], i ? `${i}-${name}` : name, {type}));
  }
  el.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
}
"""

_DRAG_JS = """
(el, kind) => {
  const dt = new DataTransfer();
  el.dispatchEvent(new DragEvent(kind, {dataTransfer: dt, bubbles: true, cancelable: true}));
}
"""

_PROMPT = "Drop image here or click to select"


@pytest.fixture
def upload_base_url(start_server: Callable[..., str]) -> str:
    return start_server("tests.e2e._upload_app", ready_path="/")


@pytest.fixture
def create_page(page: Page, upload_base_url: str) -> Page:
    page.goto(f"{upload_base_url}/admin/document/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()
    return page


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    f = tmp_path / "pixel.png"
    f.write_bytes(_PNG)
    return f


def _drop(page: Page, name: str = "pixel.png", mime: str = "image/png", count: int = 1) -> None:
    page.get_by_test_id("upload-dropzone").evaluate(
        _DROP_JS, {"name": name, "type": mime, "count": count}
    )


def test_dropzone_renders_for_image_field(create_page: Page) -> None:
    """Scenario: drag-drop zone renders for ImageType field."""
    # Given a model with an ImageType column
    # When the create form is rendered
    # Then a drop zone with its prompt is displayed
    zone = create_page.get_by_test_id("upload-dropzone")
    expect(zone).to_be_visible()
    expect(zone).to_have_text(_PROMPT)
    expect(create_page.get_by_test_id("upload-preview")).to_have_count(0)


def test_drop_shows_preview_and_sets_input(create_page: Page) -> None:
    """Scenario: file dropped on zone shows instant preview."""
    # Given the zone is visible
    # When a valid image is dropped
    _drop(create_page)

    # Then a preview appears and the hidden input holds the file
    expect(create_page.get_by_test_id("upload-preview")).to_be_visible()
    expect(create_page.get_by_test_id("cover_image-file-input")).to_have_js_property(
        "files.length", 1
    )


def test_drag_over_and_leave_toggle_state(create_page: Page) -> None:
    """Scenario: drag-over highlights the zone, drag-leave resets it."""
    # Given the zone is visible
    zone = create_page.get_by_test_id("upload-dropzone")

    # When a file is dragged over the zone
    zone.evaluate(_DRAG_JS, "dragover")

    # Then the label changes and the state is announced
    expect(zone).to_have_text("Release to upload")
    expect(create_page.get_by_role("status").filter(has_text="Release to upload")).to_have_count(1)

    # When the file is dragged away
    zone.evaluate(_DRAG_JS, "dragleave")

    # Then the zone resets
    expect(zone).to_have_text(_PROMPT)


def test_click_opens_file_picker(create_page: Page) -> None:
    """Scenario: click on zone opens the system file picker."""
    # When the user clicks the zone
    with create_page.expect_file_chooser() as chooser:
        create_page.get_by_test_id("upload-dropzone").click()

    # Then a single-file picker opens
    assert chooser.value.is_multiple() is False


@pytest.mark.parametrize("key", ["Enter", "Space"])
def test_keyboard_key_opens_picker(create_page: Page, key: str) -> None:
    """Scenario: keyboard accessibility for the drop zone."""
    # Given the zone is a button focused via keyboard
    zone = create_page.get_by_test_id("upload-dropzone")
    assert zone.evaluate("el => el.tagName") == "BUTTON"
    zone.focus()
    expect(zone).to_be_focused()

    # When the user presses the key
    # Then the file picker opens
    with create_page.expect_file_chooser():
        create_page.keyboard.press(key)


def test_invalid_type_shows_inline_error(create_page: Page) -> None:
    """Scenario: invalid file type dropped shows inline error."""
    # When a text file is dropped
    _drop(create_page, name="notes.txt", mime="text/plain")

    # Then an inline error is shown and no preview appears
    expect(
        create_page.get_by_role("alert").filter(has_text="File type not allowed")
    ).to_be_visible()
    expect(create_page.get_by_test_id("upload-preview")).to_have_count(0)


def test_multiple_files_keep_first_and_warn(create_page: Page) -> None:
    """Scenario: multiple files rejected for single-file fields."""
    # When three files are dropped at once
    _drop(create_page, count=3)

    # Then only one is kept and a warning is shown
    expect(create_page.get_by_test_id("cover_image-file-input")).to_have_js_property(
        "files.length", 1
    )
    expect(create_page.get_by_text("Only one file allowed")).to_be_visible()


def test_picker_selection_shows_preview_and_remove_clears(
    create_page: Page, png_file: Path
) -> None:
    """Scenario: choosing a file shows a preview; Remove clears it."""
    # When a file is chosen through the input
    create_page.get_by_test_id("cover_image-file-input").set_input_files(str(png_file))
    expect(create_page.get_by_test_id("upload-preview")).to_be_visible()

    # And Remove is pressed
    create_page.get_by_role("button", name="Remove").click()

    # Then the preview and the input are cleared
    expect(create_page.get_by_test_id("upload-preview")).to_have_count(0)
    expect(create_page.get_by_test_id("cover_image-file-input")).to_have_js_property(
        "files.length", 0
    )


_PROGRESS_JS = """
() => document.querySelector('form').dispatchEvent(new CustomEvent('htmx:xhr:progress', {
  bubbles: true, detail: {lengthComputable: true, loaded: 2097152, total: 5242880}
}))
"""


def test_progress_bar_shows_bytes_transferred(create_page: Page, png_file: Path) -> None:
    """Scenario: progress bar shows bytes transferred."""
    # Given a file is selected and the progress bar is hidden
    create_page.get_by_test_id("cover_image-file-input").set_input_files(str(png_file))
    progress = create_page.get_by_test_id("upload-progress")
    expect(progress).to_be_hidden()

    # When 2MB of 5MB have been transferred
    create_page.evaluate(_PROGRESS_JS)

    # Then the label reports bytes and percentage
    expect(progress).to_be_visible()
    expect(progress).to_have_attribute("aria-valuenow", "40")
    expect(progress).to_contain_text("2.0 MB / 5.0 MB (40%)")


def test_network_error_shows_retry_that_resends_file(create_page: Page, png_file: Path) -> None:
    """Scenario: network error shows Retry; Retry re-sends the same file."""
    # Given the create request fails at network level the first time
    calls: list[str] = []
    bodies: list[str] = []

    def handler(route):
        calls.append(route.request.method)
        bodies.append(
            route.request.post_data_buffer.decode("latin-1")
            if route.request.post_data_buffer
            else ""
        )
        if len(calls) == 1:
            route.abort("connectionfailed")
        else:
            route.continue_()

    create_page.route("**/admin/document", handler)
    create_page.get_by_test_id("cover_image-file-input").set_input_files(str(png_file))

    # When the form is submitted
    create_page.get_by_role("button", name="Create").click()

    # Then an error and a Retry button are shown
    expect(create_page.get_by_text("Upload failed — check your connection")).to_be_visible()
    retry = create_page.get_by_test_id("upload-retry")
    expect(retry).to_be_visible()

    # When Retry is clicked
    retry.click()

    # Then the request is sent again with the file still attached
    expect(retry).to_be_hidden()
    assert len(calls) == 2
    assert all('filename="pixel.png"' in b for b in bodies)
