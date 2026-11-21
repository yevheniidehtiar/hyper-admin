"""Render the demo tour of the docs: feature screenshots and a captioned MP4/WebM video.

Starts the ERP example (``examples.erp.main``, in-memory database, demo accounts seeded)
on a free port, walks through it with Playwright and writes:

* ``docs/assets/demo/*.png``: the screenshot tour of ``docs/demo.md`` and the README
* ``docs/assets/screenshots/{code-to-ui,list-search-filters,...}.png``: feature shots
* ``docs/assets/demo/hyperadmin-demo.{mp4,webm}`` and ``hyperadmin-demo-poster.jpg``

Usage::

    uv run python scripts/demo_tour_video.py              # screenshots and video
    uv run python scripts/demo_tour_video.py --no-video   # screenshots only

Needs Chromium for Playwright (``uv run playwright install chromium``) and ``ffmpeg``
with ``libx264`` and ``libvpx-vp9`` on ``PATH`` for the video. The video is a sequence
of still frames (crisp text, small files) joined with short cross-fades; each frame
carries a caption that names the feature on screen. All data is synthetic seed data.

On macOS, Chromium renders date and number inputs in the system locale. For en-US
inputs (as the committed assets have), render with the Linux browser of the Playwright
image, matching the installed Playwright version::

    docker run -d --rm --name tour-browser -p 127.0.0.1:3555:3000 --init --ipc=host \\
        mcr.microsoft.com/playwright:v1.63.0-noble \\
        npx -y playwright@1.63.0 run-server --port 3000 --host 0.0.0.0
    uv run python scripts/demo_tour_video.py --browser-ws ws://127.0.0.1:3555/
"""

from __future__ import annotations

import argparse
import base64
import html
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from erp_screenshots import erp_server, optimise_png
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    ViewportSize,
    expect,
    sync_playwright,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "docs" / "assets" / "demo"
SHOTS_DIR = ROOT / "docs" / "assets" / "screenshots"

# Docs screenshots: the convention of erp_screenshots.py (1440 wide, 2x).
DOCS_VIEWPORT: ViewportSize = {"width": 1440, "height": 900}
PHONE: ViewportSize = {"width": 390, "height": 844}
# Video frames: 1440x810 CSS pixels rendered at 4/3 -> 1920x1080.
VIDEO_VIEWPORT: ViewportSize = {"width": 1440, "height": 810}
VIDEO_SCALE = 4 / 3
FADE = 0.4  # seconds of cross-fade into a new scene
CUT = 0.05  # near-instant transition between frames of one scene (typing, clicks)
FPS = 25
OUTPUT_SIZE = "1600:900"  # sharp enough for UI text, keeps the files a few MB

# The backend code the tour starts from: an excerpt of examples/erp/sales.
MODEL_CODE = """\
class InvoiceStatus(str, enum.Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    PAID = "Paid"
    CANCELLED = "Cancelled"


class Invoice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(index=True, unique=True)
    date_issued: date
    date_due: date
    status: InvoiceStatus = InvoiceStatus.DRAFT
    customer_id: int = Field(foreign_key="erp_contacts.id")
    customer: Contact = Relationship()
    items: list["InvoiceItem"] = Relationship()
"""

ADMIN_CODE = """\
class InvoiceAdmin(ModelAdmin):
    nav_group = "Sales"
    list_display = ["number", "customer", "date_issued",
                    "date_due", "status", "total_amount"]
    list_filter = ["status", DateRangeFilter(field="date_due")]
    search_fields = ["number"]
    options = AdminOptions(inlines=[
        InlineModelSpec(model=InvoiceItem, fk_field="invoice_id"),
    ])

    @action(label="Mark paid", bulk=True)
    async def mark_paid(self, request, item_id, *, params=None):
        await self.adapter.update(item_id, {"status": InvoiceStatus.PAID})


site.register(Invoice, InvoiceAdmin)
admin.mount("/admin")
"""

CAPTION_JS = """([title, sub, where]) => {
  document.getElementById('demo-caption')?.remove();
  if (!title) return;
  const el = document.createElement('div');
  el.id = 'demo-caption';
  el.setAttribute('aria-hidden', 'true');
  const vertical = where === 'top' ? 'top:84px' : 'bottom:30px';
  el.style.cssText = `position:fixed;left:50%;${vertical};transform:translateX(-50%);
    z-index:2147483647;max-width:78%;padding:14px 28px;border-radius:14px;
    background:rgba(15,23,42,.93);color:#fff;text-align:center;pointer-events:none;
    font-family:Inter,system-ui,sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.35);`;
  const t = document.createElement('div');
  t.textContent = title;
  t.style.cssText = 'font-size:23px;font-weight:650;line-height:1.3';
  el.appendChild(t);
  if (sub) {
    const s = document.createElement('div');
    s.textContent = sub;
    s.style.cssText = 'font-size:16px;font-weight:450;opacity:.82;margin-top:4px';
    el.appendChild(s);
  }
  document.body.appendChild(el);
}"""

RING_JS = """(box) => {
  const el = document.createElement('div');
  el.className = 'demo-ring';
  el.setAttribute('aria-hidden', 'true');
  el.style.cssText = `position:fixed;left:${box.x - 6}px;top:${box.y - 6}px;
    width:${box.width + 12}px;height:${box.height + 12}px;border:3px solid #f59e0b;
    border-radius:12px;box-shadow:0 0 0 6px rgba(245,158,11,.22);
    z-index:2147483646;pointer-events:none;`;
  document.body.appendChild(el);
}"""

CLEAR_JS = """() => {
  document.getElementById('demo-caption')?.remove();
  document.querySelectorAll('.demo-ring').forEach((el) => el.remove());
}"""


@dataclass
class Reel:
    """The frames of the video: each one a PNG, how long it stays, and its fade in."""

    workdir: Path
    frames: list[tuple[Path, float, float]] = field(default_factory=list)
    poster: Path | None = None

    def shot(
        self,
        page: Page,
        seconds: float,
        title: str = "",
        sub: str = "",
        *,
        fade: float = FADE,
        where: str = "bottom",
        ring: Locator | None = None,
    ) -> None:
        """Caption the page, take one frame and add it to the reel."""
        page.wait_for_timeout(200)
        page.evaluate(CLEAR_JS)
        if ring is not None:
            box = ring.bounding_box()
            if box is not None:
                page.evaluate(RING_JS, box)
        page.evaluate(CAPTION_JS, [title, sub, where])
        path = self.workdir / f"frame-{len(self.frames):03d}.png"
        page.screenshot(path=path)
        page.evaluate(CLEAR_JS)
        self.frames.append((path, seconds, fade))
        sys.stdout.write(f"frame {len(self.frames):02d} {seconds:.1f}s {title}\n")

    @property
    def length(self) -> float:
        """Running time in seconds once cross-fades overlap neighbouring frames."""
        return sum(s for _, s, _ in self.frames) - sum(f for _, _, f in self.frames[1:])


def _save(page: Page, path: Path) -> None:
    page.wait_for_timeout(200)
    page.screenshot(path=path)
    optimise_png(path)
    sys.stdout.write(f"saved {path.relative_to(ROOT)}\n")


def _context(
    browser: Browser, *, video: bool = False, dark: bool = False, phone: bool = False
) -> BrowserContext:
    if phone:
        viewport, scale = PHONE, 2.0
    elif video:
        viewport, scale = VIDEO_VIEWPORT, VIDEO_SCALE
    else:
        viewport, scale = DOCS_VIEWPORT, 2.0
    return browser.new_context(
        viewport=viewport,
        device_scale_factor=scale,
        color_scheme="dark" if dark else "light",
        reduced_motion="reduce",
        locale="en-US",
    )


def _sign_in(
    page: Page,
    base: str,
    username: str = "admin",
    password: str = "admin",  # noqa: S107 - the seeded local example's public credentials
) -> None:
    page.goto(base + "/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(base + "/admin/")


def _code_html(code: str) -> str:
    return highlight(code, PythonLexer(), HtmlFormatter(nowrap=True))


def _slide_page(base: str, body: str, *, dark_bg: bool = True) -> str:
    """A full-screen HTML slide in the admin's fonts, for title and code frames."""
    style = HtmlFormatter(style="github-dark").get_style_defs(".code")
    bg = "#0b1220" if dark_bg else "#f6f8fa"
    fg = "#e6edf3" if dark_bg else "#0f172a"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Inter; src: url({base}/admin/static/fonts/InterVariable.woff2); }}
@font-face {{ font-family: JBMono; src: url({base}/admin/static/fonts/JetBrainsMonoVariable.woff2); }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; background: {bg}; color: {fg}; font-family: Inter, sans-serif; }}
.wrap {{ height: 100%; display: flex; flex-direction: column; justify-content: center; padding: 48px 64px; }}
.title {{ font-size: 64px; font-weight: 750; letter-spacing: -0.02em; margin: 0; }}
.lead {{ font-size: 28px; opacity: .8; margin: 18px 0 0; max-width: 1100px; line-height: 1.35; }}
.accent {{ color: #2dd4bf; }}
.label {{ font-size: 20px; font-weight: 650; text-transform: uppercase; letter-spacing: .08em;
          color: #2dd4bf; margin: 0 0 14px; }}
.code {{ background: #0d1117; border: 1px solid #30363d; border-radius: 14px; padding: 22px 26px;
         font-family: JBMono, monospace; font-size: 19px; line-height: 1.5; white-space: pre;
         color: #e6edf3; margin: 0; overflow: hidden; }}
.split {{ display: grid; grid-template-columns: 630px 1fr; gap: 36px; align-items: center; height: 100%; }}
.split .code {{ font-size: 12.5px; padding: 16px 18px; }}
.shot {{ width: 100%; border-radius: 12px; border: 1px solid #30363d;
         box-shadow: 0 20px 50px rgba(0,0,0,.45); display: block; }}
.arrow {{ font-size: 18px; opacity: .75; margin: 14px 0 0; }}
.phones {{ display: flex; gap: 56px; justify-content: center; align-items: center; height: 100%; }}
.phones img {{ height: 700px; border-radius: 34px; border: 10px solid #1e293b;
               box-shadow: 0 20px 50px rgba(0,0,0,.5); }}
.small {{ font-size: 22px; opacity: .75; margin-top: 26px; font-family: JBMono, monospace; }}
{style}
</style></head><body>{body}</body></html>"""


def _data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _split_body(code: str, image: Path, caption: str) -> str:
    return f"""<div class="wrap"><div class="split">
<div><p class="label">Your backend</p><pre class="code">{_code_html(code)}</pre>
<p class="arrow">{html.escape(caption)}</p></div>
<div><p class="label">The admin you get</p><img class="shot" src="{_data_uri(image)}" alt=""></div>
</div></div>"""


# ── Docs screenshots ────────────────────────────────────────────────────────────────


def render_screenshots(browser: Browser, base: str, work: Path) -> None:
    """Refresh docs/assets/demo/*.png and add the feature shots to docs/assets/screenshots."""
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    ctx = _context(browser)
    page = ctx.new_page()
    page.goto(base + "/admin/login")
    _save(page, DEMO_DIR / "login.png")
    _sign_in(page, base)
    expect(page.get_by_test_id("figure-overdue-invoices")).to_be_visible()
    _save(page, SHOTS_DIR / "dashboard.png")

    page.goto(base + "/admin/invoice")
    _save(page, DEMO_DIR / "list.png")
    page.screenshot(path=work / "list-for-split.png")

    # Search, a filter and a sort, all in the URL.
    page.goto(
        base + "/admin/invoice?search=INV-1&filter_status=Sent&sort_by=date_due&sort_direction=desc"
    )
    _save(page, SHOTS_DIR / "list-search-filters.png")

    # Bulk selection with the action bar.
    page.goto(base + "/admin/invoice")
    rows = page.get_by_test_id("list-row")
    for i in range(3):
        rows.nth(i).get_by_test_id("bulk-checkbox").check()
    expect(page.get_by_test_id("bulk-bar")).to_be_visible()
    page.get_by_test_id("bulk-action-select").select_option(label="Mark paid")
    _save(page, SHOTS_DIR / "bulk-actions.png")

    # Detail, then the edit form with the inline invoice items.
    page.goto(base + "/admin/invoice/1")  # the detail page; a row click opens the edit form
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    _save(page, DEMO_DIR / "detail.png")
    page.get_by_test_id("detail-edit-link").click()
    form = page.get_by_test_id("model-form")
    expect(form).to_be_visible()
    page.get_by_test_id("inline-invoiceitem").scroll_into_view_if_needed()
    _save(page, SHOTS_DIR / "form-inlines.png")

    # Create form, then the validation errors of an empty submit.
    page.goto(base + "/admin/invoice/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()
    _save(page, DEMO_DIR / "create.png")
    _submit_empty(page)
    _save(page, SHOTS_DIR / "form-validation.png")

    # Permissions: a group in the matrix.
    _ensure_group(page, base)
    page.goto(base + "/admin/permissions-matrix/")
    expect(page.get_by_test_id("pmatrix-table")).to_be_visible()
    _tick_matrix(page)
    _save(page, SHOTS_DIR / "permission-matrix.png")

    page.goto(base + "/admin/erp/profit-loss")
    _save(page, SHOTS_DIR / "profit-loss.png")
    ctx.close()

    # The read-only demo account: no create, edit or delete controls.
    ctx = _context(browser)
    page = ctx.new_page()
    _sign_in(page, base, "demo_ro", "demo_ro")
    page.goto(base + "/admin/invoice")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    _save(page, SHOTS_DIR / "read-only-list.png")
    ctx.close()

    # Dark mode.
    ctx = _context(browser, dark=True)
    page = ctx.new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    _save(page, DEMO_DIR / "list-dark.png")
    page.goto(base + "/admin/invoice/create")
    _submit_empty(page)
    _save(page, SHOTS_DIR / "form-validation-dark.png")
    ctx.close()

    # Phone.
    ctx = _context(browser, phone=True)
    page = ctx.new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    _save(page, DEMO_DIR / "list-mobile.png")
    ctx.close()

    # Code next to the UI it produces.
    ctx = browser.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
    page = ctx.new_page()
    page.goto(base + "/admin/login")
    body = _split_body(
        MODEL_CODE + "\n\n" + ADMIN_CODE,
        work / "list-for-split.png",
        "Columns, filters, search, inline items and the bulk action all come from these lines.",
    )
    page.set_content(_slide_page(base, body))
    page.wait_for_timeout(300)
    _save(page, SHOTS_DIR / "code-to-ui.png")
    ctx.close()


def _submit_empty(page: Page) -> None:
    page.get_by_test_id("form-actions").get_by_role("button", name="Create").click()
    expect(page.get_by_test_id("error-summary")).to_be_visible()


def _tick_matrix(page: Page) -> None:
    """Tick a few grants (left unsaved) so the matrix shows its pending-changes bar."""
    for model, count in (("contact", 1), ("invoice", 3), ("invoiceitem", 3)):
        boxes = page.get_by_test_id(f"pmatrix-row-{model}").get_by_role("checkbox")
        for i in range(count):
            boxes.nth(i).check()


def _ensure_group(page: Page, base: str) -> None:
    """Create the "Bookkeepers" group once (in-memory demo database only)."""
    page.goto(base + "/admin/group?q=Bookkeepers")
    if page.get_by_test_id("list-row").count():
        return
    page.goto(base + "/admin/group/create")
    page.get_by_label("Name").fill("Bookkeepers")
    page.get_by_test_id("form-actions").get_by_role("button", name="Create").click()
    page.wait_for_load_state("networkidle")


# ── Video ───────────────────────────────────────────────────────────────────────────


def record_reel(browser: Browser, base: str, reel: Reel) -> None:
    """Walk the ERP demo and collect the captioned frames of the video."""
    ctx = _context(browser, video=True)
    page = ctx.new_page()
    page.goto(base + "/admin/login")

    # 1. Title (and the poster: the same card with a play button), then the backend code.
    title = (
        '<div class="wrap"><p class="label">HyperAdmin · product tour</p>'
        '<h1 class="title">Define the backend.<br><span class="accent">Get the admin UI.</span></h1>'
        '<p class="lead">A Django-admin style interface for FastAPI, generated from your '
        "SQLModel or SQLAlchemy models. No JavaScript build, no second schema.</p></div>"
    )
    play = (
        '<div style="position:fixed;right:120px;top:50%;transform:translateY(-50%);width:150px;'
        "height:150px;border-radius:50%;background:#2dd4bf;display:flex;align-items:center;"
        'justify-content:center;box-shadow:0 16px 40px rgba(0,0,0,.45)">'
        '<div style="margin-left:14px;width:0;height:0;border-top:34px solid transparent;'
        'border-bottom:34px solid transparent;border-left:56px solid #0b1220"></div></div>'
    )
    page.set_content(_slide_page(base, title + play))
    page.wait_for_timeout(200)
    reel.poster = reel.workdir / "poster.png"
    page.screenshot(path=reel.poster)
    page.set_content(_slide_page(base, title))
    reel.shot(page, 4.0, fade=0)
    page.set_content(
        _slide_page(
            base,
            '<div class="wrap"><p class="label">1 · Your models</p>'
            f'<pre class="code">{_code_html(MODEL_CODE)}</pre></div>',
        )
    )
    reel.shot(page, 5.0)
    page.set_content(
        _slide_page(
            base,
            '<div class="wrap"><p class="label">2 · A few admin options</p>'
            f'<pre class="code">{_code_html(ADMIN_CODE)}</pre></div>',
        )
    )
    reel.shot(page, 6.0)

    # 2. Sign in and the dashboard.
    page.goto(base + "/admin/login")
    reel.shot(page, 2.5, "Built-in session login", "Or plug in your own auth with ExternalAuth")
    _sign_in(page, base)
    expect(page.get_by_test_id("figure-overdue-invoices")).to_be_visible()
    reel.shot(
        page, 3.2, "A dashboard page, added through the plugin API", "Figures load after the page"
    )

    # 3. The list.
    page.goto(base + "/admin/invoice")
    page.screenshot(path=reel.workdir / "list-for-split.png")
    page.set_content(
        _slide_page(
            base,
            _split_body(
                ADMIN_CODE, reel.workdir / "list-for-split.png", "These lines become this page."
            ),
        )
    )
    reel.shot(page, 4.5)
    page.goto(base + "/admin/invoice")
    reel.shot(
        page,
        3.8,
        "List view generated from list_display",
        "Enum fields become coloured status pills; relations show their name",
    )
    search = page.get_by_test_id("search-input")
    search.click()
    for chunk in ("I", "NV-", "1"):
        search.press_sequentially(chunk, delay=40)  # keyup drives the HTMX search
        reel.shot(
            page,
            0.7,
            "Search across search_fields",
            "Results update as you type",
            fade=CUT,
            ring=search,
        )
    page.wait_for_timeout(1200)  # the 500 ms debounce plus the swap
    reel.shot(
        page,
        1.8,
        "Search across search_fields",
        "Results update as you type",
        fade=CUT,
        ring=search,
    )

    page.goto(base + "/admin/invoice?filter_status=Sent")
    reel.shot(
        page,
        3.4,
        "Filters from list_filter",
        "Status, customer, due-date range, and a custom Overdue filter",
        ring=page.get_by_test_id("filter-sidebar"),
    )
    sort = page.get_by_test_id("sort-date_due")
    sort.click()
    page.wait_for_load_state("networkidle")
    reel.shot(
        page, 2.6, "Click a column to sort", "Sort, filters and page all live in the URL", ring=sort
    )
    nxt = page.get_by_test_id("pagination-next")
    nxt.scroll_into_view_if_needed()
    reel.shot(
        page,
        2.6,
        "Pagination and page size",
        where="top",
        ring=page.get_by_test_id("pagination-info"),
    )

    # 4. Bulk action with a result per row.
    page.goto(base + "/admin/invoice")
    rows = page.get_by_test_id("list-row")
    for i in range(4):
        rows.nth(i).get_by_test_id("bulk-checkbox").check()
    expect(page.get_by_test_id("bulk-bar")).to_be_visible()
    page.get_by_test_id("bulk-action-select").select_option(label="Mark paid")
    reel.shot(
        page,
        3.2,
        "Bulk actions from @action(bulk=True)",
        "Select rows, pick the action, run it",
        ring=page.get_by_test_id("bulk-bar"),
    )
    page.get_by_test_id("bulk-run-btn").click()
    confirm = page.get_by_test_id("bulk-confirm-btn")
    if confirm.is_visible():
        confirm.click()
    expect(page.get_by_test_id("bulk-result")).to_be_visible(timeout=15000)
    reel.shot(
        page,
        3.6,
        "A result for every row",
        "Invoices that are not Sent are refused, with the reason",
    )

    # 5. Detail and edit with inlines.
    page.goto(base + "/admin/invoice")
    page.goto(base + "/admin/invoice/1")  # the detail page; a row click opens the edit form
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    reel.shot(page, 3.0, "Detail view with tabbed panels", "Custom actions sit next to the record")
    page.get_by_test_id("detail-edit-link").click()
    expect(page.get_by_test_id("model-form")).to_be_visible()
    reel.shot(
        page,
        3.2,
        "Edit form generated from the field types",
        "Dates, enums and foreign keys get the right widget",
    )
    page.get_by_test_id("inline-invoiceitem").scroll_into_view_if_needed()
    reel.shot(
        page,
        3.4,
        "Related rows edited inline",
        "InlineModelSpec: the invoice items on the invoice page",
        ring=page.get_by_test_id("inline-invoiceitem"),
    )

    # 6. Create with validation.
    page.goto(base + "/admin/invoice/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()
    reel.shot(page, 2.6, "Create form", "Required fields come from the model")
    _submit_empty(page)
    reel.shot(
        page,
        3.6,
        "Server-side validation",
        "An error summary and an error under each field",
        ring=page.get_by_test_id("error-summary"),
    )

    # 7. Command palette.
    page.goto(base + "/admin/invoice")
    page.keyboard.press("ControlOrMeta+k")
    palette = page.get_by_test_id("palette-input")
    expect(palette).to_be_visible()
    reel.shot(page, 1.4, "⌘K command palette", "Jump to any model, page or record", where="top")
    for text in ("j", "jou", "journal"):
        palette.fill(text)
        page.wait_for_timeout(350 if text == "journal" else 120)
        reel.shot(
            page,
            0.6,
            "⌘K command palette",
            "Jump to any model, page or record",
            fade=CUT,
            where="top",
        )
    reel.shot(
        page, 1.6, "⌘K command palette", "Jump to any model, page or record", fade=CUT, where="top"
    )
    page.keyboard.press("Escape")

    # 8. Dark mode.
    page.goto(base + "/admin/invoice")
    toggle = page.get_by_test_id("theme-toggle")
    reel.shot(page, 1.4, "Light and dark themes", ring=toggle)
    toggle.click()
    page.wait_for_timeout(300)
    reel.shot(
        page, 3.0, "Light and dark themes", "Follows the OS, or the toggle in the navbar", fade=0.3
    )
    toggle.click()

    # 9. Permissions.
    _ensure_group(page, base)
    page.goto(base + "/admin/permissions-matrix/")
    expect(page.get_by_test_id("pmatrix-table")).to_be_visible()
    _tick_matrix(page)
    reel.shot(
        page, 3.6, "Permissions matrix", "Grant view, add, change and delete per group and model"
    )
    ctx.close()

    ro = _context(browser, video=True)
    page = ro.new_page()
    _sign_in(page, base, "demo_ro", "demo_ro")
    page.goto(base + "/admin/invoice")
    reel.shot(
        page,
        3.4,
        "A read-only user: rows open read-only, no delete buttons",
        "The server refuses anything their permissions do not allow",
    )
    ro.close()

    # 10. Phone width.
    phone = _context(browser, phone=True)
    page = phone.new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    page.wait_for_timeout(300)
    page.screenshot(path=reel.workdir / "phone-list.png")
    page.get_by_test_id("sidebar-toggle").click()
    expect(page.get_by_test_id("sidebar")).to_be_visible()
    page.wait_for_timeout(300)
    page.screenshot(path=reel.workdir / "phone-sidebar.png")
    phone.close()

    ctx = _context(browser, video=True)
    page = ctx.new_page()
    page.goto(base + "/admin/login")
    page.set_content(
        _slide_page(
            base,
            '<div class="phones">'
            f'<img src="{_data_uri(reel.workdir / "phone-list.png")}" alt="">'
            f'<img src="{_data_uri(reel.workdir / "phone-sidebar.png")}" alt="">'
            "</div>",
        )
    )
    reel.shot(
        page,
        3.6,
        "Responsive down to phone width",
        "Rows become cards; the sidebar becomes a drawer",
    )

    # 11. Reports.
    _sign_in(page, base)
    page.goto(base + "/admin/erp/profit-loss")
    reel.shot(
        page,
        3.2,
        "Your own pages inside the admin",
        "A Profit & Loss report, linked from the sidebar",
    )

    # 12. End card.
    page.set_content(
        _slide_page(
            base,
            '<div class="wrap"><h1 class="title">Define the backend.<br>'
            '<span class="accent">Get the admin UI.</span></h1>'
            '<p class="small">pip install hyper-admin</p>'
            '<p class="lead">Docs: yevheniidehtiar.github.io/hyper-admin<br>'
            "Live demo: hyper-admin-demo.onrender.com/admin (demo / demo)</p></div>",
        )
    )
    reel.shot(page, 5.0)
    ctx.close()


def encode(reel: Reel, out_dir: Path) -> None:
    """Join the frames with cross-fades and encode MP4 (H.264), WebM (VP9) and a poster."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is not on PATH: install it or pass --no-video")
    args: list[str] = [ffmpeg, "-y", "-loglevel", "error"]
    for path, seconds, _ in reel.frames:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(path)]
    graph = [
        f"[{i}:v]scale={OUTPUT_SIZE}:flags=lanczos,setsar=1,format=yuv420p[v{i}]"
        for i in range(len(reel.frames))
    ]
    last, elapsed = "v0", reel.frames[0][1]
    for i, (_, seconds, wanted_fade) in enumerate(reel.frames[1:], start=1):
        fade = max(wanted_fade, CUT)
        elapsed -= fade
        graph.append(
            f"[{last}][v{i}]xfade=transition=fade:duration={fade:.3f}:offset={elapsed:.3f}[x{i}]"
        )
        last, elapsed = f"x{i}", elapsed + seconds
    filter_complex = ";".join(graph)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / "hyperadmin-demo.mp4"
    webm = out_dir / "hyperadmin-demo.webm"
    # Long keyframe intervals: most frames are stills, so keyframes are the main cost.
    common = [
        *args,
        *("-filter_complex", filter_complex, "-map", f"[{last}]"),
        *("-r", str(FPS), "-g", str(FPS * 10), "-an"),
    ]
    h264 = ("-c:v", "libx264", "-preset", "veryslow", "-crf", "28", "-tune", "stillimage")
    subprocess.run(  # noqa: S603 - fixed argv
        [*common, *h264, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)],
        check=True,
    )
    vp9 = ("-c:v", "libvpx-vp9", "-crf", "44", "-b:v", "0", "-row-mt", "1")
    subprocess.run(  # noqa: S603 - fixed argv
        [*common, *vp9, "-deadline", "good", "-cpu-used", "2", str(webm)],
        check=True,
    )
    poster = out_dir / "hyperadmin-demo-poster.jpg"
    subprocess.run(  # noqa: S603 - fixed argv
        [
            *(ffmpeg, "-y", "-loglevel", "error", "-i", str(reel.poster or reel.frames[0][0])),
            *("-vf", "scale=1280:720:flags=lanczos", "-q:v", "3", str(poster)),
        ],
        check=True,
    )
    for path in (mp4, webm, poster):
        sys.stdout.write(f"saved {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.2f} MB)\n")
    sys.stdout.write(f"video length {reel.length:.1f}s\n")


def render(
    base: str,
    *,
    screenshots: bool,
    video: bool,
    browser_ws: str | None = None,
    browser_host: str | None = None,
) -> None:
    """Render the screenshots and/or the video against a running ERP example."""
    with tempfile.TemporaryDirectory(prefix="hyperadmin-tour-") as tmp, sync_playwright() as pw:
        work = Path(tmp)
        if browser_ws:
            # A remote (Linux) browser: en-US date and number inputs on any host OS.
            browser = pw.chromium.connect(browser_ws)
            if browser_host:
                base = base.replace("127.0.0.1", browser_host)
        else:
            # On macOS date and number inputs follow the system locale, whatever --lang says.
            browser = pw.chromium.launch(args=["--lang=en-US"])
        if screenshots:
            render_screenshots(browser, base, work)
        if video:
            reel = Reel(work)
            record_reel(browser, base, reel)
            encode(reel, DEMO_DIR)
        browser.close()


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments, start the ERP example and render the tour."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--no-video", action="store_true", help="only render the screenshots")
    parser.add_argument("--no-screenshots", action="store_true", help="only render the video")
    parser.add_argument(
        "--base-url",
        help="use a running ERP example started with HYPERADMIN_DEMO=1 and the admin password 'admin'",
    )
    parser.add_argument(
        "--browser-ws",
        help="connect to a Playwright browser server instead of launching Chromium "
        "(see the docstring for the Docker command)",
    )
    parser.add_argument(
        "--browser-host",
        default="host.docker.internal",
        help="host name the remote browser uses to reach this machine",
    )
    args = parser.parse_args(argv)

    def run(base: str) -> None:
        render(
            base,
            screenshots=not args.no_screenshots,
            video=not args.no_video,
            browser_ws=args.browser_ws,
            browser_host=args.browser_host,
        )

    if args.base_url:
        run(args.base_url.rstrip("/"))
        return
    with erp_server(
        extra_env={"HYPERADMIN_DEMO": "1", "HYPERADMIN_ADMIN_PASSWORD": "admin"}
    ) as base:
        run(base)


if __name__ == "__main__":
    main()
