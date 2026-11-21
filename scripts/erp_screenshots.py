"""Render the navigation and list screenshots of the docs from the ERP example.

Starts ``examples.erp.main`` on a free port (in-memory database, seeded on startup),
signs in as ``admin`` and saves one PNG per feature to ``docs/assets/screenshots/``:

    uv run python scripts/erp_screenshots.py [--out docs/assets/screenshots]

Needs Chromium for Playwright (``uv run playwright install chromium``). The shots are
for documentation, not regression tests: re-render them when the UI they show changes.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from playwright.sync_api import Browser, Page, ViewportSize, expect, sync_playwright

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parents[1]
DESKTOP: ViewportSize = {"width": 1440, "height": 900}
PHONE: ViewportSize = {"width": 390, "height": 844}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def erp_server(timeout: float = 120.0, extra_env: dict[str, str] | None = None) -> Iterator[str]:
    """Run the ERP example with a fresh in-memory database; yield its base URL."""
    port = _free_port()
    env = {**os.environ, "E2E_TESTING": "1", "DEMO_REALTIME": "0", **(extra_env or {})}
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [sys.executable, "-m", "uvicorn", "examples.erp.main:app", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                urllib.request.urlopen(base + "/", timeout=2)  # noqa: S310 - local URL
                break
            except OSError:
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("the ERP example did not start") from None
                time.sleep(1)
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _sign_in(page: Page, base: str) -> None:
    page.goto(base + "/admin/login")
    page.get_by_label("Username").fill("admin")
    page.get_by_label("Password").fill("admin")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base + "/admin/")


def _new_page(browser: Browser, base: str, *, dark: bool = False, phone: bool = False) -> Page:
    context = browser.new_context(
        viewport=PHONE if phone else DESKTOP,
        device_scale_factor=2,
        color_scheme="dark" if dark else "light",
        reduced_motion="reduce",
    )
    page = context.new_page()
    _sign_in(page, base)
    return page


def optimise_png(path: Path) -> None:
    """Shrink a UI screenshot in place: a 256-colour palette keeps flat UI and text crisp."""
    with Image.open(path) as img:
        palette = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    palette.save(path, optimize=True)


def _shoot(page: Page, out: Path, name: str) -> None:
    page.wait_for_timeout(150)  # let focus rings and tooltips settle
    page.screenshot(path=out / f"{name}.png")
    optimise_png(out / f"{name}.png")
    sys.stdout.write(f"saved {name}\n")


def render(base: str, out: Path, browser_ws: str | None = None) -> None:
    """Save every screenshot to ``out``, with a local or a remote (``browser_ws``) Chromium."""
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.connect(browser_ws) if browser_ws else pw.chromium.launch()

        # Grouped sidebar with pinned pages, light and dark.
        page = _new_page(browser, base)
        page.get_by_test_id("nav-pin-invoice").click()
        expect(page.get_by_test_id("nav-pinned")).to_contain_text("Invoices")
        page.get_by_test_id("nav-pin-account").click()
        expect(page.get_by_test_id("nav-pinned")).to_contain_text("Accounts")
        page.goto(base + "/admin/invoice")
        _shoot(page, out, "sidebar-groups-pinned")

        # Icon rail.
        page.get_by_test_id("sidebar-rail-toggle").click()
        _shoot(page, out, "sidebar-rail")
        page.get_by_test_id("sidebar-rail-toggle").click()

        # Clickable rows: hover a row, then the delete confirmation.
        rows = page.get_by_test_id("list-row")
        rows.nth(2).hover()
        _shoot(page, out, "list-rows")
        rows.nth(2).get_by_test_id("row-delete-btn").click()
        expect(page.get_by_role("alertdialog")).to_be_visible()
        _shoot(page, out, "delete-dialog")
        page.keyboard.press("Escape")

        # Command palette: search by group name.
        page.keyboard.press("ControlOrMeta+k")
        page.get_by_test_id("palette-input").fill("acco")
        _shoot(page, out, "command-palette")
        page.keyboard.press("Escape")

        # Keyboard: row focus with j, then the ? overlay. Start from no hover and no focus.
        page.mouse.move(0, DESKTOP["height"] - 1)
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("j")
        page.keyboard.press("j")
        _shoot(page, out, "keyboard-row-focus")
        page.keyboard.press("?")
        expect(page.get_by_test_id("shortcuts-overlay")).to_be_visible()
        _shoot(page, out, "shortcuts-overlay")
        page.keyboard.press("Escape")

        # Form safety: a dirty edit form with the sticky save bar.
        rows.first.get_by_test_id("row-link").click()
        form = page.get_by_test_id("model-form")
        expect(form).to_be_visible()
        form.get_by_role("textbox").first.fill("Edited, not saved")
        page.mouse.wheel(0, 600)
        _shoot(page, out, "form-sticky-save-bar")
        page.context.close()

        # Dark mode.
        page = _new_page(browser, base, dark=True)
        page.goto(base + "/admin/invoice")
        _shoot(page, out, "list-rows-dark")
        page.keyboard.press("ControlOrMeta+k")
        page.get_by_test_id("palette-input").fill("inv")
        _shoot(page, out, "command-palette-dark")
        page.context.close()

        # Phone: list cards and the sidebar drawer.
        page = _new_page(browser, base, phone=True)
        page.goto(base + "/admin/invoice")
        _shoot(page, out, "phone-list")
        page.get_by_test_id("sidebar-toggle").click()
        expect(page.get_by_test_id("sidebar")).to_be_visible()
        _shoot(page, out, "phone-sidebar")
        page.context.close()

        browser.close()


def main() -> None:
    """Parse arguments, start the ERP example and render the screenshots."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "assets" / "screenshots")
    parser.add_argument("--base-url", help="use a running ERP example instead of starting one")
    parser.add_argument(
        "--browser-ws",
        help="connect to a Playwright browser server (see scripts/demo_tour_video.py)",
    )
    parser.add_argument(
        "--browser-host",
        default="host.docker.internal",
        help="host name the remote browser uses to reach this machine",
    )
    args = parser.parse_args()
    if args.base_url:
        render(args.base_url.rstrip("/"), args.out, args.browser_ws)
        return
    with erp_server() as local_base:
        base = local_base.replace("127.0.0.1", args.browser_host) if args.browser_ws else local_base
        render(base, args.out, args.browser_ws)


if __name__ == "__main__":
    main()
