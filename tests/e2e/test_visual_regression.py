"""Visual-regression baseline for the responsive design epic (C3-D).

Captures full-page screenshots of four key views (list, create, detail, login)
at three breakpoints (375, 768, 1024) and compares against committed baseline
PNGs in ``tests/e2e/snapshots/responsive/``.

To regenerate baselines after an intentional visual change::

    RESPONSIVE_SNAPSHOTS_UPDATE=1 uv run pytest tests/e2e/test_visual_regression.py
    git add tests/e2e/snapshots/responsive/
    git commit -m "test(e2e): refresh responsive visual baselines"

The diff metric is the percentage of image pixels that differ from the baseline
by more than 30/255 in any channel. Up to 1% of the image may differ before a
test fails — that tolerance absorbs font antialiasing variance and small focus/
hover/cursor artifacts (typically < 0.5%) without ignoring real layout changes
(sidebar reappearing on mobile, tables losing their card layout, headings
shifting), which shift many pixels at once and easily clear the threshold.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import Page

SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "responsive"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

UPDATE_BASELINES = os.environ.get("RESPONSIVE_SNAPSHOTS_UPDATE") == "1"

# Threshold for "is this pixel meaningfully different?" — max channel diff out of 255.
# Below this, the difference is dominated by font antialiasing and sub-pixel timing.
PIXEL_DIFF_THRESHOLD = 30

# Maximum fraction of the full image allowed to differ by more than the
# per-pixel threshold above. Layout-level regressions shift large fractions
# of the image (sidebar reappearing, table card collapse, header row change)
# and easily exceed 1%. Localized hover/focus/cursor variance stays below 0.5%.
MAX_DIFFERING_FRACTION = 0.01

VIEWPORTS = {
    "375px": {"width": 375, "height": 667},
    "768px": {"width": 768, "height": 1024},
    "1024px": {"width": 1024, "height": 768},
}


def _route(view: str) -> str:
    """Path under demo_base_url for each baseline view."""
    return {
        "list": "/admin/user",
        "create": "/admin/product/create",
        "detail": "/admin/country/1",
    }[view]


def _capture_or_compare(page: Page, view: str, viewport_name: str) -> None:
    """Take a full-page screenshot and either write the baseline or diff it.

    On baseline write, the PNG is left in the working tree so the user can
    `git add` it. On comparison, the test fails when more than
    ``MAX_DIFFERING_FRACTION`` of pixels differ by more than
    ``PIXEL_DIFF_THRESHOLD`` per channel.
    """
    snapshot_path = SNAPSHOT_DIR / f"{view}-{viewport_name}.png"
    actual_bytes = page.screenshot(full_page=True)

    if UPDATE_BASELINES or not snapshot_path.exists():
        snapshot_path.write_bytes(actual_bytes)
        if not UPDATE_BASELINES:
            pytest.skip(f"baseline created at {snapshot_path}; commit and re-run to compare")
        return

    baseline = Image.open(snapshot_path).convert("RGB")
    actual = Image.open(io.BytesIO(actual_bytes)).convert("RGB")

    if baseline.size != actual.size:
        pytest.fail(
            f"viewport size mismatch for {view}@{viewport_name}: "
            f"baseline {baseline.size} vs actual {actual.size}"
        )

    diff = ImageChops.difference(baseline, actual)
    if diff.getbbox() is None:
        return  # pixel-perfect match

    # Count pixels that differ by more than the per-pixel threshold across
    # the WHOLE image, not just the diff bbox — this gives a stable
    # denominator that doesn't blow up small localized AA noise.
    total_pixels = baseline.size[0] * baseline.size[1]
    raw = diff.tobytes()  # flat R,G,B,R,G,B,... bytes
    significantly_different = sum(
        1
        for i in range(0, len(raw), 3)
        if max(raw[i], raw[i + 1], raw[i + 2]) > PIXEL_DIFF_THRESHOLD
    )
    differing_fraction = significantly_different / total_pixels

    if differing_fraction > MAX_DIFFERING_FRACTION:
        diff_path = SNAPSHOT_DIR / f"{view}-{viewport_name}.diff.png"
        actual_path = SNAPSHOT_DIR / f"{view}-{viewport_name}.actual.png"
        diff.save(diff_path)
        Path(actual_path).write_bytes(actual_bytes)
        pytest.fail(
            f"{view}@{viewport_name} visual diff: "
            f"{significantly_different} / {total_pixels} pixels "
            f"({differing_fraction * 100:.2f}%) differ by > "
            f"{PIXEL_DIFF_THRESHOLD}/255 — exceeds "
            f"{MAX_DIFFERING_FRACTION * 100:.2f}% threshold. "
            f"Inspect {diff_path} and {actual_path}, then either fix the "
            f"regression or run with RESPONSIVE_SNAPSHOTS_UPDATE=1 to refresh."
        )


# ---------------------------------------------------------------------------
# Baselines — list view
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS.keys()))
def test_list_view_baseline(page: Page, demo_base_url: str, viewport_name: str) -> None:
    """
    Scenario: screenshot baseline captured at {viewport_name}.

      Given viewport is the named breakpoint
      When  the list view loads
      Then  the captured screenshot matches the committed baseline
    """
    page.set_viewport_size(VIEWPORTS[viewport_name])
    page.goto(demo_base_url + _route("list"))
    page.wait_for_load_state("networkidle")
    _capture_or_compare(page, "list", viewport_name)


# ---------------------------------------------------------------------------
# Baselines — create view
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS.keys()))
def test_create_view_baseline(page: Page, demo_base_url: str, viewport_name: str) -> None:
    """Capture/compare baseline of the product create form per viewport."""
    page.set_viewport_size(VIEWPORTS[viewport_name])
    page.goto(demo_base_url + _route("create"))
    page.wait_for_load_state("networkidle")
    _capture_or_compare(page, "create", viewport_name)


# ---------------------------------------------------------------------------
# Baselines — detail view
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS.keys()))
def test_detail_view_baseline(page: Page, demo_base_url: str, viewport_name: str) -> None:
    """Capture/compare baseline of the country detail view per viewport."""
    page.set_viewport_size(VIEWPORTS[viewport_name])
    page.goto(demo_base_url + _route("detail"))
    page.wait_for_load_state("networkidle")
    _capture_or_compare(page, "detail", viewport_name)


# ---------------------------------------------------------------------------
# Baselines — login view (separate fixture because login is on the auth app)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS.keys()))
def test_login_view_baseline(page: Page, auth_base_url: str, viewport_name: str) -> None:
    """Capture/compare baseline of the login page per viewport."""
    page.set_viewport_size(VIEWPORTS[viewport_name])
    page.goto(f"{auth_base_url}/admin/login")
    page.wait_for_load_state("networkidle")
    _capture_or_compare(page, "login", viewport_name)
