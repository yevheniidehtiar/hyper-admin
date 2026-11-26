"""Render the demo tour of the docs: feature screenshots and a captioned MP4/WebM video.

The video shows what sets HyperAdmin apart for a backend-only team (presence, conflict
resolution, speed on large tables, load testing, plugins, auth, the widget set), not the
create/edit/delete pages every admin has. It boots the apps it needs from this repository,
each on a free port with a throwaway database:

=============  ==============================================  ==============================
key            app                                             used by
=============  ==============================================  ==============================
``erp``        ``examples.erp.main`` (demo accounts, realtime)  most scenes, pivot reports
``occ``        ``tests.e2e.apps.occ_conflict``                 the conflict dialog
``scale``      ``tests.e2e.apps.scalability`` (1.2 M rows)     the speed scene
``dashboard``  ``tests.e2e.apps.dashboard_builder``            dashboard widgets
``logfire``    ``examples/full-demo`` (with Logfire)           Logfire spans
``tasks``      ``tests.e2e.apps.tasks_monitoring``             the tasks plugin
``oauth``      ``tests.e2e.apps.oauth``                        the SSO login button
``palette``    ``tests.e2e.apps.palette_app``                  record search in the palette
=============  ==============================================  ==============================

Every figure on screen is measured during the run (response times, SQL statements, the
seeding and the Locust run) or quoted from ``docs/compatibility.md`` and labelled so.

Outputs:

* ``docs/assets/demo/hyperadmin-demo.{mp4,webm}`` and ``hyperadmin-demo-poster.jpg``
* ``docs/assets/demo/*.png``: the screenshot tour of ``docs/demo.md`` and the README
* ``docs/assets/screenshots/*.png``: one shot per feature scene (``Reel.shot(save_as=...)``),
  the ERP shots of ``docs/demo.md`` and the palette record search of the navigation guide

Usage::

    uv sync --all-extras --all-packages
    uv run python scripts/demo_tour_video.py                   # everything
    uv run python scripts/demo_tour_video.py --no-screenshots  # the video only
    uv run python scripts/demo_tour_video.py --no-video        # the docs screenshots only
    uv run python scripts/demo_tour_video.py --list-scenes
    uv run python scripts/demo_tour_video.py --scenes presence,conflict --frames /tmp/f

``--scenes`` renders a subset into ``--frames`` (PNG frames, no encoding) to check one
scene after a UI change. A full run takes ten minutes or more, most of it the load-test
scene: it waits for a quiet host (up to 25 minutes, then stops) and runs each Locust
measurement twice.

Each scene is one ``scene_*`` function listed in ``SCENES``: reorder, drop or retime
scenes there. Needs Chromium for Playwright (``uv run playwright install chromium``),
``ffmpeg`` with ``libx264`` and ``libvpx-vp9`` on ``PATH``, and ``locust`` (the
``loadtest`` extra). The video is a sequence of still frames (crisp text, small files)
joined with short cross-fades; captions are DOM overlays.

On macOS, Chromium renders date and number inputs in the system locale. For en-US inputs
(as the committed assets have), render with the Linux browser of the Playwright image,
matching the installed Playwright version::

    docker run -d --rm --name tour-browser -p 127.0.0.1:3555:3000 --init --ipc=host \\
        mcr.microsoft.com/playwright:v1.63.0-noble \\
        npx -y playwright@1.63.0 run-server --port 3000 --host 0.0.0.0
    uv run python scripts/demo_tour_video.py --browser-ws ws://127.0.0.1:3555/

The OAuth scene always uses a local Chromium: its stand-in identity provider is served by
the app itself, and the server must reach it under the same address as the browser.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erp_screenshots import _free_port, app_server, optimise_png
from PIL import Image
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    ViewportSize,
    expect,
    sync_playwright,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # tests.e2e.apps.scalability_models seeds the large tables

DEMO_DIR = ROOT / "docs" / "assets" / "demo"
SHOTS_DIR = ROOT / "docs" / "assets" / "screenshots"

# Docs screenshots: the convention of erp_screenshots.py (1440 wide, 2x).
DOCS_VIEWPORT: ViewportSize = {"width": 1440, "height": 900}
PHONE: ViewportSize = {"width": 390, "height": 844}
# Video frames: 1440x810 CSS pixels rendered at 4/3 -> 1920x1080.
VIDEO_VIEWPORT: ViewportSize = {"width": 1440, "height": 810}
VIDEO_SCALE = 4 / 3
# One browser of a two-user scene, shown at half width next to the other.
PAIR_VIEWPORT: ViewportSize = {"width": 1200, "height": 960}
FADE = 0.4  # seconds of cross-fade into a new scene
CUT = 0.05  # near-instant transition between frames of one scene (typing, clicks)
FPS = 25
OUTPUT_SIZE = "1600:900"  # sharp enough for UI text, keeps the files a few MB
SCALE = 100  # multiplier of tests.e2e.apps.scalability_models: 100 gives 1.2 M rows
LOCUST_USERS = 20
LOCUST_SECONDS = 30
LOCUST_REPEATS = 2  # the first run of each measurement warms the file cache; the last one shows
# The runs start only on a quiet host: load average and CPU idle, held for QUIET_HOLD seconds.
QUIET_LOAD = 2.0
QUIET_IDLE = 85.0
QUIET_HOLD = 120.0
QUIET_WAIT = 25 * 60.0
# Montage crops left out of the closing grid of the widgets scene.
GRID_SKIP = ("Bulk actions", "Pagination", "Enum select", "Grouped sidebar", "Task queues")

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
  // A popover joins the top layer above an open modal <dialog> (the command palette),
  // which would otherwise cover or dim the caption.
  el.setAttribute('popover', 'manual');
  // 'right': bottom right, over the empty space under the screenshot of a split slide.
  const place = where === 'top' ? 'left:50%;top:84px;transform:translateX(-50%);max-width:80%'
    : where === 'right' ? 'right:64px;bottom:60px;max-width:640px'
    : 'left:50%;bottom:30px;transform:translateX(-50%);max-width:80%';
  el.style.cssText = `position:fixed;inset:auto;margin:0;border:0;${place};
    z-index:2147483647;padding:14px 28px;border-radius:0;
    background:rgba(14,16,13,.95);color:#f1f3ec;text-align:center;pointer-events:none;
    border:1px solid #2a2f27;border-top:3px solid #b8f23e;
    font-family:Inter,system-ui,sans-serif;box-shadow:0 12px 32px rgba(0,0,0,.35);`;
  const t = document.createElement('div');
  t.textContent = title;
  t.style.cssText = 'font-size:23px;font-weight:650;line-height:1.3';
  el.appendChild(t);
  if (sub) {
    const s = document.createElement('div');
    s.textContent = sub;
    s.style.cssText = 'font-size:16px;font-weight:450;opacity:.84;margin-top:4px';
    el.appendChild(s);
  }
  document.body.appendChild(el);
  el.showPopover();
}"""

RING_JS = """(box) => {
  const el = document.createElement('div');
  el.className = 'demo-ring';
  el.setAttribute('aria-hidden', 'true');
  el.style.cssText = `position:fixed;left:${box.x - 6}px;top:${box.y - 6}px;
    width:${box.width + 12}px;height:${box.height + 12}px;border:3px solid #ffb547;
    border-radius:0;box-shadow:0 0 0 6px rgba(255,181,71,.24);
    z-index:2147483646;pointer-events:none;`;
  document.body.appendChild(el);
}"""

# A card of measured figures, pinned to the top right of the page.
METRICS_JS = """([title, rows, note]) => {
  const el = document.createElement('div');
  el.className = 'demo-metrics';
  el.setAttribute('aria-hidden', 'true');
  el.style.cssText = `position:fixed;right:22px;top:76px;width:410px;z-index:2147483646;
    padding:18px 22px;border-radius:0;background:rgba(14,16,13,.96);color:#d3d8cc;
    border:1px solid #2a2f27;
    font-family:Inter,system-ui,sans-serif;box-shadow:0 16px 40px rgba(0,0,0,.4);
    pointer-events:none;`;
  const h = document.createElement('div');
  h.textContent = title;
  h.style.cssText = 'font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#b8f23e;margin-bottom:10px;font-family:JetBrains Mono,ui-monospace,monospace';
  el.appendChild(h);
  for (const [label, value] of rows) {
    const r = document.createElement('div');
    r.style.cssText = 'display:flex;justify-content:space-between;gap:16px;padding:6px 0;border-top:1px solid #2a2f27;font-size:15px';
    const l = document.createElement('span'); l.textContent = label; l.style.opacity = '.85';
    const v = document.createElement('b'); v.textContent = value; v.style.cssText = 'color:#f1f3ec;white-space:nowrap;font-family:JetBrains Mono,ui-monospace,monospace;font-weight:500';
    r.append(l, v); el.appendChild(r);
  }
  if (note) {
    const n = document.createElement('div');
    n.textContent = note;
    n.style.cssText = 'font-size:12px;opacity:.65;margin-top:10px;line-height:1.4';
    el.appendChild(n);
  }
  document.body.appendChild(el);
}"""

CLEAR_JS = """() => {
  document.getElementById('demo-caption')?.remove();
  document.querySelectorAll('.demo-ring').forEach((el) => el.remove());
}"""

TTFB_JS = """() => {
  const nav = performance.getEntriesByType('navigation')[0];
  return nav.responseStart - nav.requestStart;
}"""


@dataclass
class Reel:
    """The frames of the video: each one a PNG, how long it stays, and its fade in."""

    workdir: Path
    frames: list[tuple[Path, float, float]] = field(default_factory=list)
    poster: Path | None = None
    save_shots: bool = True

    def shot(  # noqa: PLR0913 - every keyword is a per-frame choice of a scene
        self,
        page: Page,
        seconds: float,
        title: str = "",
        sub: str = "",
        *,
        fade: float = FADE,
        where: str = "bottom",
        ring: Locator | None = None,
        save_as: Path | None = None,
    ) -> None:
        """Caption the page, take one frame and add it to the reel.

        ``save_as`` also writes the uncaptioned page (with its ring) as a docs screenshot.
        """
        page.wait_for_timeout(200)
        page.evaluate(CLEAR_JS)
        if ring is not None:
            box = ring.bounding_box()
            if box is not None:
                page.evaluate(RING_JS, box)
        if save_as is not None and self.save_shots:
            _save(page, save_as)
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


# ── Apps ────────────────────────────────────────────────────────────────────────────


@dataclass
class Apps:
    """Starts each app the first time a scene asks for it; stops them all at the end."""

    stack: ExitStack
    work: Path
    browser_host: str | None = None  # host name a remote browser uses for this machine
    urls: dict[str, str] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)  # measured while starting apps

    def url(self, key: str, *, for_browser: bool = True) -> str:
        """Base URL of app ``key``, as the (possibly remote) browser reaches it."""
        if key not in self.urls:
            self.urls[key] = self._start(key)
        base = self.urls[key]
        if for_browser and self.browser_host and key != "oauth":
            return base.replace("127.0.0.1", self.browser_host)
        return base

    def log(self, key: str) -> Path:
        return self.work / f"{key}.log"

    def _start(self, key: str) -> str:
        e2e = {"E2E_TESTING": "1"}
        if key == "erp":
            env = {
                **e2e,
                "HYPERADMIN_DEMO": "1",
                "HYPERADMIN_ADMIN_PASSWORD": "admin",
                "DEMO_REALTIME": "1",
            }
            return self._run("examples.erp.main", env, ready="/")
        if key == "scale":
            from tests.e2e.apps.scalability_models import seed_database  # noqa: PLC0415

            db = self.work / "scale.db"
            started = time.perf_counter()
            rows = seed_database(db, SCALE)
            self.facts["seed_rows"] = rows
            self.facts["seed_seconds"] = time.perf_counter() - started
            env = {**e2e, "E2E_SCALABILITY_DB": str(db), "E2E_SCALABILITY_SCALE": str(SCALE)}
            return self._run("tests.e2e.apps.scalability", env)
        if key == "oauth":
            port = _free_port()
            env = {**e2e, "E2E_OAUTH_IDP_URL": f"http://127.0.0.1:{port}"}
            return self._run("tests.e2e.apps.oauth", env, port=port)
        if key == "logfire":
            # Without E2E_TESTING the full demo turns on Logfire, which prints its spans to
            # the log; it then keeps examples/full-demo/full_demo.db, removed again below.
            db = ROOT / "examples" / "full-demo" / "full_demo.db"
            if not db.exists():
                self.stack.callback(db.unlink, missing_ok=True)
            return self._run("tests.e2e.apps.full_demo", {"E2E_TESTING": ""})
        if key == "palette":
            env = {**e2e, "HYPERADMIN_E2E_PALETTE_DB": str(self.work / "palette.db")}
            return self._run("tests.e2e.apps.palette_app", env)
        modules = {
            "occ": "tests.e2e.apps.occ_conflict",
            "tasks": "tests.e2e.apps.tasks_monitoring",
            "dashboard": "tests.e2e.apps.dashboard_builder",
        }
        return self._run(modules[key], e2e)

    def _run(
        self, module: str, env: dict[str, str], *, port: int | None = None, ready: str = ""
    ) -> str:
        key = module.rsplit(".", 1)[-1]
        server = app_server(
            module,
            env=env,
            port=port,
            log=self.work / f"{key}.log",
            ready_path=ready or "/admin/login",
        )
        base = self.stack.enter_context(server)
        sys.stdout.write(f"started {module} at {base}\n")
        return base


# ── Helpers ─────────────────────────────────────────────────────────────────────────


@dataclass
class Tour:
    """Everything a scene needs."""

    pw: Playwright
    browser: Browser
    apps: Apps
    reel: Reel
    work: Path
    _local: Browser | None = None

    def local_browser(self) -> Browser:
        """A Chromium on this machine (the OAuth scene's provider must share its address)."""
        if self._local is None:
            self._local = self.pw.chromium.launch(args=["--lang=en-US"])
        return self._local

    def page(self, *, dark: bool = False, browser: Browser | None = None) -> Page:
        return _context(browser or self.browser, video=True, dark=dark).new_page()

    def slide(self, body: str) -> Page:
        """A fresh page showing a full-screen slide."""
        page = self.page()
        base = self.apps.url("erp")
        page.goto(base + "/admin/login")  # same origin, so the slide can load the fonts
        page.set_content(_slide_page(base, body))
        page.wait_for_timeout(250)
        return page


def _save(page: Page, path: Path) -> None:
    page.wait_for_timeout(200)
    page.screenshot(path=path)
    optimise_png(path)
    sys.stdout.write(f"saved {path.relative_to(ROOT)}\n")


def _context(
    browser: Browser,
    *,
    video: bool = False,
    dark: bool = False,
    phone: bool = False,
    pair: bool = False,
) -> BrowserContext:
    if phone:
        viewport, scale = PHONE, 2.0
    elif pair:
        viewport, scale = PAIR_VIEWPORT, 1.0
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
    """A full-screen HTML slide in the admin's fonts, for title, code and terminal frames."""
    style = HtmlFormatter(style="github-dark").get_style_defs(".code")
    # The terminal theme preset's palette (src/hyperadmin/static/css/_theme-terminal.css).
    bg = "#0e100d" if dark_bg else "#f3f4ef"
    fg = "#f1f3ec" if dark_bg else "#0e100d"
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: Inter; src: url({base}/admin/static/fonts/InterVariable.woff2); }}
@font-face {{ font-family: JBMono; src: url({base}/admin/static/fonts/JetBrainsMonoVariable.woff2); }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; height: 100%; background: {bg}; color: {fg}; font-family: Inter, sans-serif; }}
.wrap {{ height: 100%; display: flex; flex-direction: column; justify-content: center; padding: 48px 64px; }}
.title {{ font-size: 58px; font-weight: 500; letter-spacing: -0.01em; margin: 0;
          font-family: JBMono, monospace; line-height: 1.2; }}
.lead {{ font-size: 28px; opacity: .8; margin: 18px 0 0; max-width: 1150px; line-height: 1.35; }}
.accent {{ color: #b8f23e; }}
.label {{ font-size: 18px; font-weight: 500; text-transform: uppercase; letter-spacing: .08em;
          color: #b8f23e; margin: 0 0 14px; font-family: JBMono, monospace;
          display: flex; align-items: center; gap: 14px; }}
.label img {{ width: 40px; height: 40px; }}
.code {{ background: #0a0b09; border: 1px solid #2a2f27; border-radius: 0; padding: 22px 26px;
         font-family: JBMono, monospace; font-size: 19px; line-height: 1.5; white-space: pre;
         color: #e6edf3; margin: 0; overflow: hidden; }}
.split {{ display: grid; grid-template-columns: 630px 1fr; gap: 36px; align-items: center; height: 100%; }}
.split .code {{ font-size: 12.5px; padding: 16px 18px; }}
.shot {{ width: 100%; border-radius: 0; border: 1px solid #2a2f27;
         box-shadow: 0 20px 50px rgba(0,0,0,.45); display: block; }}
.arrow {{ font-size: 18px; opacity: .75; margin: 14px 0 0; }}
.pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 26px; padding: 30px 32px 0; }}
.pair figure {{ margin: 0; }}
.pair figcaption {{ font-size: 16px; font-weight: 500; margin: 0 0 8px; color: #9aa293;
                     font-family: JBMono, monospace; }}
.pair figcaption b {{ color: #b8f23e; font-weight: 500; }}
.phones {{ display: flex; gap: 56px; justify-content: center; align-items: center; height: 100%; }}
.phones img {{ height: 700px; border-radius: 34px; border: 10px solid #1c2018;
               box-shadow: 0 20px 50px rgba(0,0,0,.5); }}
.small {{ font-size: 22px; opacity: .75; margin-top: 26px; font-family: JBMono, monospace; }}
.term {{ background: #0a0b09; border: 1px solid #2a2f27; border-radius: 0; padding: 20px 24px;
         font-family: JBMono, monospace; font-size: 15px; line-height: 1.55; white-space: pre;
         color: #d3d8cc; margin: 0; overflow: hidden; }}
.term .cmd {{ color: #b8f23e; }}
.term .dim {{ color: #9aa293; }}
.term .hi {{ color: #f1f3ec; font-weight: 700; }}
.cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 22px; }}
.card {{ background: #161915; border: 1px solid #2a2f27; border-radius: 0; padding: 14px 18px; }}
.card b {{ display: block; font-size: 28px; color: #b8f23e; font-family: JBMono, monospace;
           font-weight: 500; }}
.card span {{ font-size: 15px; opacity: .75; }}
.widget {{ height: 100%; display: flex; flex-direction: column; align-items: center;
           justify-content: center; padding: 40px 60px 150px; }}
.widget img {{ max-width: 1150px; max-height: 560px; border-radius: 0; background: #fff;
               box-shadow: 0 20px 50px rgba(0,0,0,.5); }}
.widget .label {{ margin-bottom: 22px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 30px 40px 0; }}
.grid figure {{ margin: 0; background: #fff; border-radius: 0; overflow: hidden; height: 196px;
                border: 1px solid #2a2f27; }}
.grid img {{ width: 100%; height: 100%; object-fit: cover; object-position: left top; }}
{style}
.code {{ background: #0a0b09; }}
</style></head><body>{body}</body></html>"""


def _data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _split_body(code: str, image: Path, caption: str) -> str:
    return f"""<div class="wrap"><div class="split">
<div><p class="label">Your backend</p><pre class="code">{_code_html(code)}</pre>
<p class="arrow">{html.escape(caption)}</p></div>
<div><p class="label">The admin you get</p><img class="shot" src="{_data_uri(image)}" alt=""></div>
</div></div>"""


def _pair_body(left: tuple[str, Path], right: tuple[str, Path]) -> str:
    """Two browsers side by side, each under a ``<b>who</b> · what`` label."""
    figures = "".join(
        f'<figure><figcaption>{label}</figcaption><img class="shot" src="{_data_uri(img)}" alt="">'
        "</figure>"
        for label, img in (left, right)
    )
    return f'<div class="pair">{figures}</div>'


def _pair_frame(t: Tour, left: tuple[str, Page], right: tuple[str, Page], name: str) -> Page:
    """Screenshot two pages and return a slide that shows them side by side."""
    shots = []
    for i, (label, page) in enumerate((left, right)):
        page.wait_for_timeout(150)
        path = t.work / f"{name}-{i}.png"
        page.screenshot(path=path)
        shots.append((label, path))
    return t.slide(_pair_body(shots[0], shots[1]))


def _ttfb(page: Page, url: str, runs: int = 5) -> float:
    """Median time to first byte of ``url`` over ``runs`` loads, as the browser measured it."""
    samples = []
    for _ in range(runs):
        page.goto(url)
        samples.append(float(page.evaluate(TTFB_JS)))
    return statistics.median(samples)


def _ms(value: float) -> str:
    return f"{value:.0f} ms" if value >= 10 else f"{value:.1f} ms"


# ── Scenes ──────────────────────────────────────────────────────────────────────────
# Each scene adds its frames to the reel. Keep them independent: --scenes runs any subset.


def scene_title(t: Tour) -> None:
    """Title card, also rendered with a play button as the video poster."""
    title = (
        '<div class="wrap"><p class="label">'
        f'<img src="{t.apps.url("erp")}/admin/static/img/terminal/hyperadmin-mark.svg" alt="">'
        "HyperAdmin · product tour</p>"
        '<h1 class="title">Define the backend.<br><span class="accent">Get the admin UI.</span></h1>'
        '<p class="lead">A Django-admin style interface for FastAPI, generated from your '
        "SQLModel or SQLAlchemy models. No frontend code, no JavaScript build.</p></div>"
    )
    play = (
        '<div style="position:fixed;right:120px;top:50%;transform:translateY(-50%);width:150px;'
        "height:150px;border-radius:0;background:#b8f23e;display:flex;align-items:center;"
        'justify-content:center;box-shadow:0 16px 40px rgba(0,0,0,.45)">'
        '<div style="margin-left:14px;width:0;height:0;border-top:34px solid transparent;'
        'border-bottom:34px solid transparent;border-left:56px solid #0e100d"></div></div>'
    )
    page = t.slide(title + play)
    t.reel.poster = t.work / "poster.png"
    page.screenshot(path=t.reel.poster)
    page.set_content(_slide_page(t.apps.url("erp"), title))
    page.wait_for_timeout(200)
    t.reel.shot(page, 4.0, fade=0)
    page.context.close()


def scene_code(t: Tour) -> None:
    """The model and admin code next to the list it generates."""
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    list_png = t.work / "list-for-split.png"
    page.screenshot(path=list_png)
    page.set_content(
        _slide_page(
            base,
            _split_body(
                MODEL_CODE + "\n" + ADMIN_CODE,
                list_png,
                "That is the whole admin for invoices: list, filters, search, forms, actions.",
            ),
        )
    )
    page.wait_for_timeout(250)
    t.reel.shot(
        page,
        6.0,
        "You write models and a few options",
        "HyperAdmin generates every page from them. Nobody on the team writes frontend code.",
        where="right",
        save_as=SHOTS_DIR / "code-to-ui.png",
    )
    page.context.close()


def scene_sso(t: Tour) -> None:
    """The login page with an OAuth provider button (local browser, see the docstring)."""
    base = t.apps.url("oauth")
    page = t.page(browser=t.local_browser())
    page.goto(base + "/admin/login")
    button = page.get_by_test_id("oauth-btn-google")
    expect(button).to_be_visible()
    t.reel.shot(
        page,
        3.4,
        "Sign-in built in: passwords, MFA and OAuth single sign-on",
        "Google and GitHub presets, or any OAuth 2 provider; a first SSO login creates the user",
        ring=button,
        save_as=SHOTS_DIR / "oauth-login.png",
    )
    page.context.close()


def scene_permissions(t: Tour) -> None:
    """The permissions matrix, then the same list as a read-only user."""
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    _ensure_group(page, base)
    page.goto(base + "/admin/permissions-matrix/")
    expect(page.get_by_test_id("pmatrix-table")).to_be_visible()
    _tick_matrix(page)
    t.reel.shot(
        page,
        3.4,
        "Permissions per group and model, on one screen",
        "View, add, change and delete for every model, plus actions and detail panels",
    )
    page.context.close()

    page = t.page()
    _sign_in(page, base, "demo_ro", "demo_ro")
    page.goto(base + "/admin/invoice")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    t.reel.shot(
        page,
        3.2,
        "A read-only user gets a read-only admin",
        "No Create or Delete buttons, rows open read-only; the server refuses what is not granted",
    )
    page.context.close()


def scene_presence(t: Tour) -> None:
    """Two users on the same invoice see each other, then a save refreshes the other's list."""
    base = t.apps.url("erp")
    alice = _context(t.browser, pair=True).new_page()
    bob = _context(t.browser, pair=True).new_page()
    _sign_in(alice, base, "admin", "admin")
    _sign_in(bob, base, "demo2", "demo2")
    edit = base + "/admin/invoice/1/edit"
    alice.goto(edit)
    bob.goto(edit)
    expect(alice.get_by_test_id("presence-banner")).to_contain_text("demo2", timeout=15000)
    expect(bob.get_by_test_id("presence-banner")).to_contain_text("admin", timeout=15000)
    slide = _pair_frame(
        t,
        ("<b>admin</b> · editing invoice 1", alice),
        ("<b>demo2</b> · same invoice, another browser", bob),
        "presence",
    )
    t.reel.shot(
        slide,
        5.0,
        "Presence: see who else is on a record, live",
        "One WebSocket, no extra service, no frontend code: realtime=RealtimeSettings()",
        save_as=SHOTS_DIR / "presence.png",
    )
    slide.context.close()

    # Live list: admin watches the list while demo2 saves a change.
    alice.goto(base + "/admin/invoice")
    alice.get_by_test_id("sidebar-rail-toggle").click()  # room for the Status column
    expect(alice.get_by_test_id("realtime-status")).to_be_visible()
    alice.wait_for_timeout(800)
    form = bob.get_by_test_id("model-form")
    status = form.get_by_label("Status")
    current = status.input_value()
    new_status = "Cancelled" if current != "Cancelled" else "Draft"
    status.select_option(new_status)
    form.get_by_role("button", name="Update").click()
    row = alice.locator('tr[data-pk="1"]')
    expect(row).to_contain_text(new_status, timeout=15000)
    alice.evaluate(RING_JS, row.bounding_box())
    slide = _pair_frame(
        t,
        ("<b>admin</b> · on the invoice list, no reload", alice),
        (f"<b>demo2</b> · set invoice 1 to {new_status}", bob),
        "live",
    )
    t.reel.shot(
        slide,
        4.6,
        "Live lists: other people's changes appear without a reload",
        "The row updates in place; creates and deletes also show a toast naming who did it",
        fade=0.3,
        save_as=SHOTS_DIR / "live-updates.png",
    )
    slide.context.close()
    alice.context.close()
    bob.context.close()


def scene_conflict(t: Tour) -> None:
    """Optimistic concurrency: the second of two saves gets the conflict dialog."""
    base = t.apps.url("occ")
    alice = _context(t.browser, pair=True).new_page()
    bob = _context(t.browser, pair=True).new_page()
    for page in (alice, bob):
        _sign_in(page, base, "alice", "secret123")
        page.goto(base + "/admin/order/42/edit")
    alice.get_by_label("Customer").fill("Acme Holding")
    bob.get_by_label("Customer").fill("Acme Ltd")
    slide = _pair_frame(
        t,
        ("<b>Browser 1</b> · editing order ORD-1042", alice),
        ("<b>Browser 2</b> · the same order, at the same time", bob),
        "race",
    )
    t.reel.shot(slide, 3.2, "Two people edit the same record", "Most admins: the last save wins")
    slide.context.close()

    bob.get_by_role("button", name="Update").click()
    expect(bob).to_have_url(base + "/admin/order")
    alice.get_by_role("button", name="Update").click()
    expect(alice.get_by_test_id("conflict-dialog")).to_be_visible()
    alice.close()

    # The dialog on a full-size page.
    page = t.page()
    _sign_in(page, base, "alice", "secret123")
    page.goto(base + "/admin/order/42/edit")
    page.get_by_label("Customer").fill("Acme Holding")
    other = _context(t.browser).new_page()
    _sign_in(other, base, "alice", "secret123")
    other.goto(base + "/admin/order/42/edit")
    other.get_by_label("Customer").fill("Acme Ltd")
    other.get_by_role("button", name="Update").click()
    other.context.close()
    page.get_by_role("button", name="Update").click()
    dialog = page.get_by_test_id("conflict-dialog")
    expect(dialog).to_be_visible()
    t.reel.shot(
        page,
        5.0,
        "No silent overwrites: the second save gets a conflict dialog",
        "Your edit next to the stored value, field by field. One option: enforce_occ=True",
        ring=page.get_by_test_id("conflict-diff"),
        save_as=SHOTS_DIR / "conflict-dialog.png",
    )
    page.get_by_test_id("conflict-override").click()
    expect(page).to_have_url(base + "/admin/order")
    t.reel.shot(
        page,
        2.4,
        "Resolved in one click",
        "Override with your value, or discard your edits and reload the current row",
        fade=0.3,
    )
    page.context.close()
    bob.context.close()


def scene_scale(t: Tour) -> None:
    """A 1.2-million-row database: cursor pages, relations in one query, cached totals."""
    base = t.apps.url("scale")
    rows = t.apps.facts["seed_rows"]
    page = t.page()
    _sign_in(page, base, "alice", "secret123")
    movements = 3_000 * SCALE
    products = 9_000 * SCALE

    # Cursor pagination: the first page and one 25 rows from the end cost the same.
    from hyperadmin.core.adapters import encode_cursor  # noqa: PLC0415

    after = movements - 25
    deep = f"{base}/admin/movement?cursor={encode_cursor(after, after, 'next')}"
    first_ms = _ttfb(page, base + "/admin/movement")
    deep_ms = _ttfb(page, deep)
    page.request.post(base + "/_test/reset")
    page.goto(deep)
    reads = _statements(page, base, "e2e_sc_movement")
    page.evaluate(
        METRICS_JS,
        [
            "Measured in this recording",
            [
                ["Rows in the database", f"{rows:,}"],
                [f"Page 1 of {movements:,} movements", _ms(first_ms)],
                [f"Row {after:,} (keyset page)", _ms(deep_ms)],
                ["SQL reads of the table, deep page", str(len(reads))],
                ["count(*) on cursor pages", "none"],
            ],
            (
                "Server time to first byte, median of 5 loads. SQLite file, one uvicorn "
                'worker, on a laptop. pagination_mode="cursor".'
            ),
        ],
    )
    t.reel.shot(
        page,
        5.8,
        "Fast on large tables, out of the box",
        "Keyset pagination: the last pages cost the same as page 1",
        save_as=SHOTS_DIR / "scale-cursor.png",
    )
    page.evaluate("() => document.querySelectorAll('.demo-metrics').forEach(e => e.remove())")

    # Relations in one query whatever the page size, and a cached total.
    counts = {}
    for size in (10, 100):
        page.request.post(base + "/_test/reset")
        page.goto(f"{base}/admin/product?page_size={size}")
        counts[size] = len(_statements(page, base, "e2e_sc_supplier"))
    page.request.post(base + "/_test/reset")
    cold = _ttfb(page, f"{base}/admin/product?search=SKU-0000&page_size=10", runs=1)
    warm = _ttfb(page, f"{base}/admin/product?search=SKU-0000&page_size=10", runs=5)
    page.goto(f"{base}/admin/product?page_size=10")
    page.evaluate(
        METRICS_JS,
        [
            "Measured in this recording",
            [
                [f"{products:,} products, with supplier", ""],
                ["Supplier queries, 10 rows per page", str(counts[10])],
                ["Supplier queries, 100 rows per page", str(counts[100])],
                ["Search, first request (counts)", _ms(cold)],
                ["Same search, total cached", _ms(warm)],
            ],
            (
                "Relations in list_display load with one SELECT ... IN per page (no N+1). "
                "count_cache_ttl=60 reuses the total."
            ),
        ],
    )
    t.reel.shot(
        page,
        5.4,
        "No N+1 queries, cached totals",
        "On by default; tune per model in AdminOptions",
        save_as=SHOTS_DIR / "scale-relations.png",
    )
    page.context.close()


def scene_loadtest(t: Tour) -> None:
    """The load-test tooling: the seeding above, then a read run and a write run with Locust."""
    t.apps.url("scale")  # seeds the large tables, timed
    rows, seconds = t.apps.facts["seed_rows"], t.apps.facts["seed_seconds"]
    host = _host_facts()
    read = _measure(t, "ReadUser", QUIET_HOLD)
    write = _measure(t, "WriteUser", 30.0)
    body = (
        '<div class="wrap" style="padding-bottom:150px">'
        '<p class="label">Load testing ships with it</p>'
        '<pre class="term">'
        '<span class="cmd">$ hyperadmin seed</span>'
        '<span class="dim">   # hyperadmin.loadtest BulkSeeder: realistic rows, skewed foreign keys</span>\n'
        f'  this run: <span class="hi">{rows:,} rows</span> in '
        f'<span class="hi">{seconds:.1f} s</span> (SQLite file)\n\n'
        f'<span class="cmd">$ locust --headless -u {LOCUST_USERS} -t {LOCUST_SECONDS}s</span>'
        '<span class="dim">   # each run: log in, warm up, reset stats, then measure</span>\n'
        f"{html.escape(_locust_table('READ', read))}\n"
        f"{html.escape(_locust_table('WRITE', write))}</pre>"
        '<div class="cards">'
        f"{_locust_card('Reads', read)}{_locust_card('Writes', write)}"
        '<div class="card"><b>296 req/s</b><span>Quoted, not this run: PostgreSQL, 400 users, '
        "9 CPUs, 21 ms median, 170 ms p95 (load-test matrix, docs/compatibility.md)</span></div>"
        "</div>"
        f'<p class="arrow" style="font-size:15px">This run: {LOCUST_USERS} users, {LOCUST_SECONDS} s per measurement, '
        f"logins and warm-up excluded, each measurement run {LOCUST_REPEATS} times and the last "
        f"shown (the first warms the file cache); {host['machine']}, idle host (load below "
        f"{QUIET_LOAD:.0f}, CPU idle above {QUIET_IDLE:.0f}% before the runs), SQLite file, one "
        "uvicorn worker, Locust on the same machine. Search is a substring match "
        f"(ILIKE '%term%') over {9_000 * SCALE:,} SKUs: a table scan, see the Performance guide.</p></div>"
    )
    page = t.slide(body)
    t.reel.shot(
        page,
        7.5,
        "Know your capacity before go-live",
        "Seed millions of rows, measure reads and writes separately, find the slow endpoint first",
        save_as=SHOTS_DIR / "loadtest.png",
    )
    page.context.close()


def scene_plugins(t: Tour) -> None:
    """Dashboard widgets, the ERP pivot reports, the tasks plugin and Logfire spans."""
    base = t.apps.url("dashboard")
    page = t.page()
    _sign_in(page, base, "alice", "secret123")
    grid = page.get_by_test_id("dashboard-grid")
    expect(grid).to_be_visible()
    expect(page.get_by_test_id("widget-loading")).to_have_count(0, timeout=15000)
    t.reel.shot(
        page,
        3.6,
        "Plugins: dashboard widgets from your reports",
        "Stats, charts and quick actions per permission; a failing widget never breaks the page",
        save_as=SHOTS_DIR / "dashboard-widgets.png",
    )
    page.context.close()

    # Pivot reports: the ERP registers two, listed on the plugin's "All reports" page.
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    page.get_by_test_id("sidebar").get_by_role("link", name="All reports").click()
    expect(page.get_by_test_id("report-index")).to_be_visible()
    caption = (
        "Pivot reports with a chart and CSV / XLSX export",
        "Declare dimensions and measures in Python; the index, grid, chart and exports follow",
    )
    t.reel.shot(page, 2.0, *caption)
    page.get_by_test_id("report-link-invoices-by-status").click()
    expect(page.get_by_test_id("chart-frame").first).to_be_visible(timeout=15000)
    t.reel.shot(page, 3.2, *caption, fade=0.3, save_as=SHOTS_DIR / "report-chart.png")
    page.context.close()

    # Logfire: the span tree of a list request, as the full demo printed it.
    base = t.apps.url("logfire")
    page = t.page()
    _sign_in(page, base, "alice", "secret123")
    page.goto(base + "/admin/order")
    page.wait_for_timeout(1200)
    spans = _logfire_spans(t.apps.log("full_demo"), "GET /admin/order")
    page.context.close()

    base = t.apps.url("tasks")
    page = t.page()
    _sign_in(page, base, "alice", "secret123")
    page.goto(base + "/admin/tasks/list")
    expect(page.get_by_test_id("tasks-list-row").first).to_be_visible()
    t.reel.shot(
        page,
        3.2,
        "Background tasks, monitored in the admin",
        "Queues, states, schedules and failed tasks with their traceback and a Retry button",
        save_as=SHOTS_DIR / "tasks.png",
    )
    page.context.close()

    body = (
        '<div class="wrap"><p class="label">hyperadmin-logfire · instrument_admin(admin)</p>'
        f'<pre class="term">{spans}</pre>'
        '<p class="arrow">The full-demo example\'s own console output for one list request.</p>'
        "</div>"
    )
    page = t.slide(body)
    t.reel.shot(
        page,
        3.8,
        "Logfire traces: a span per request, its SQL nested",
        "One call after admin.mount(); no token needed to see them locally",
        save_as=SHOTS_DIR / "logfire-spans.png",
    )
    page.context.close()


def scene_palette(t: Tour) -> None:
    """The command palette, typed in short steps."""
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    page.keyboard.press("ControlOrMeta+k")
    palette = page.get_by_test_id("palette-input")
    expect(palette).to_be_visible()
    caption = ("⌘K command palette", "Jump to any model, page or record from the keyboard")
    t.reel.shot(page, 1.0, *caption)
    for text in ("j", "jou", "journal"):
        palette.fill(text)
        page.wait_for_timeout(350 if text == "journal" else 120)
        t.reel.shot(page, 0.5, *caption, fade=CUT)
    t.reel.shot(page, 1.4, *caption, fade=CUT)
    page.context.close()


def scene_i18n(t: Tour) -> None:
    """The navbar language switcher: the list in Ukrainian, then right to left in Arabic.

    Ukrainian is the one bundled catalog compiled in full. The other 18 ship machine drafts
    marked fuzzy (docs/specs/i18n-top-20-locales.md), which render English until a native
    speaker reviews them, so the Arabic frame shows the mirrored layout, not Arabic text.
    """
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    switcher = page.locator("#locale-switcher")
    t.reel.shot(
        page,
        1.6,
        "Each user picks a language",
        "From the switcher in the navbar, or the browser's Accept-Language header",
        ring=switcher,
    )
    for locale, seconds, title, sub in (
        (
            "uk",
            2.8,
            "Switched to Ukrainian: the built-in strings follow",
            "20 locales bundled: Ukrainian is reviewed, the other 18 are drafts awaiting review",
        ),
        (
            "ar",
            2.8,
            "Right-to-left layout for Arabic and Hebrew",
            "The page mirrors; Arabic text appears once its draft translation is reviewed",
        ),
    ):
        switcher.select_option(locale)
        page.wait_for_load_state("networkidle")
        expect(page.locator("html")).to_have_attribute("lang", locale.replace("_", "-"))
        t.reel.shot(
            page,
            seconds,
            title,
            sub,
            fade=0.3,
            ring=switcher,
            save_as=SHOTS_DIR / ("i18n-rtl.png" if locale == "ar" else f"i18n-{locale}.png"),
        )
    switcher.select_option("en")
    page.wait_for_load_state("networkidle")
    page.context.close()


def scene_dark(t: Tour) -> None:
    """Dark mode with the navbar toggle."""
    base = t.apps.url("erp")
    page = t.page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    toggle = page.get_by_test_id("theme-toggle")
    toggle.click()
    page.wait_for_timeout(300)
    t.reel.shot(page, 2.6, "Light and dark themes", "Follows the OS, or the toggle in the navbar")
    toggle.click()
    page.context.close()


def scene_mobile(t: Tour) -> None:
    """The list and the sidebar drawer at phone width, side by side."""
    base = t.apps.url("erp")
    phone = _context(t.browser, phone=True).new_page()
    _sign_in(phone, base)
    phone.goto(base + "/admin/invoice")
    phone.wait_for_timeout(300)
    phone.screenshot(path=t.work / "phone-list.png")
    phone.get_by_test_id("sidebar-toggle").click()
    expect(phone.get_by_test_id("sidebar")).to_be_visible()
    phone.wait_for_timeout(300)
    phone.screenshot(path=t.work / "phone-sidebar.png")
    phone.context.close()
    page = t.slide(
        '<div class="phones">'
        f'<img src="{_data_uri(t.work / "phone-list.png")}" alt="">'
        f'<img src="{_data_uri(t.work / "phone-sidebar.png")}" alt="">'
        "</div>"
    )
    t.reel.shot(
        page, 3.2, "Responsive down to phone width", "Rows become cards; the sidebar is a drawer"
    )
    page.context.close()


def scene_widgets(t: Tour) -> None:
    """A fast montage of the distinct widgets, each cropped from a real page, then all of them."""
    crops = _widget_crops(t)
    page = t.slide("")
    erp = t.apps.url("erp")
    for i, (name, path) in enumerate(crops):
        page.set_content(
            _slide_page(
                erp,
                f'<div class="widget"><p class="label">{html.escape(name)}</p>'
                f'<img src="{_data_uri(path)}" alt=""></div>',
            )
        )
        page.wait_for_timeout(120)
        t.reel.shot(
            page,
            0.75,
            "Every widget comes from your field types and options",
            f"{i + 1} / {len(crops)}",
            fade=0.15 if i else FADE,
        )
    tiles = "".join(
        f'<figure><img src="{_data_uri(p)}" alt="" style="object-fit:{_tile_fit(p)}"></figure>'
        for _, p in _grid_tiles(crops)
    )
    page.set_content(_slide_page(erp, f'<div class="grid">{tiles}</div>'))
    page.wait_for_timeout(200)
    t.reel.shot(
        page,
        2.8,
        f"{len(crops)} components, zero lines of frontend code",
        "Server-rendered HTML with HTMX: no build step, no JavaScript to maintain",
        fade=0.3,
        save_as=SHOTS_DIR / "widgets.png",
    )
    page.context.close()


def scene_end(t: Tour) -> None:
    """The closing card: the backend-only use case."""
    page = t.slide(
        '<div class="wrap"><h1 class="title">Your team writes the backend.<br>'
        '<span class="accent">HyperAdmin ships the admin UI.</span></h1>'
        '<p class="lead">Realtime, conflict handling, scale, plugins and auth are already in it.</p>'
        '<p class="small">pip install hyper-admin</p>'
        '<p class="lead">Docs: yevheniidehtiar.github.io/hyper-admin<br>'
        "Live demo: hyper-admin-demo.onrender.com/admin (demo / demo)</p></div>"
    )
    t.reel.shot(page, 5.4)
    page.context.close()


SCENES: list[tuple[str, Callable[[Tour], None]]] = [
    ("title", scene_title),
    ("code", scene_code),
    ("presence", scene_presence),
    ("conflict", scene_conflict),
    ("scale", scene_scale),
    ("loadtest", scene_loadtest),
    ("plugins", scene_plugins),
    ("sso", scene_sso),
    ("permissions", scene_permissions),
    ("palette", scene_palette),
    ("i18n", scene_i18n),
    ("dark", scene_dark),
    ("mobile", scene_mobile),
    ("widgets", scene_widgets),
    ("end", scene_end),
]


# ── Scene helpers ───────────────────────────────────────────────────────────────────


def _statements(page: Page, base: str, table: str) -> list[dict[str, Any]]:
    """SQL the scalability app ran since its last reset that reads from ``table``."""
    statements = page.request.get(base + "/_test/queries").json()["statements"]
    return [s for s in statements if f"FROM {table}" in s["sql"]]


def _cpu_idle() -> float | None:
    """CPU idle percent over the next two seconds (macOS ``top``, Linux ``/proc/stat``)."""
    if os.uname().sysname == "Darwin":
        out = subprocess.run(
            ["/usr/bin/top", "-l", "2", "-n", "0", "-s", "2"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        found = re.findall(r"([\d.]+)% idle", out)
        return float(found[-1]) if found else None
    stat = Path("/proc/stat")
    if not stat.exists():
        return None
    before = [int(x) for x in stat.read_text().split()[1:8]]
    time.sleep(2)
    after = [int(x) for x in stat.read_text().split()[1:8]]
    delta = [b - a for a, b in zip(before, after, strict=True)]
    return 100 * (delta[3] + delta[4]) / max(sum(delta), 1)


def _host_sample() -> dict[str, float | None]:
    """Load average (1 minute) and CPU idle percent right now."""
    return {"load": os.getloadavg()[0], "idle": _cpu_idle()}


def _quiet(sample: dict[str, float | None]) -> bool:
    load, idle = sample["load"] or 0.0, sample["idle"]
    return load < QUIET_LOAD and (idle is None or idle > QUIET_IDLE)


def _wait_for_quiet(hold: float) -> None:
    """Block until the host has been quiet for ``hold`` seconds, or stop the tour.

    A busy host queues the requests behind other processes and the percentiles measure the
    machine, not the admin. Quiet: 1-minute load average below ``QUIET_LOAD`` and CPU idle
    above ``QUIET_IDLE`` percent at every check, 30 s apart.
    """
    deadline = time.monotonic() + QUIET_WAIT
    since: float | None = None
    while True:
        sample = _host_sample()
        now = time.monotonic()
        sys.stdout.write(f"host load {sample['load']:.2f}, idle {sample['idle']}%\n")
        since = (since or now) if _quiet(sample) else None
        if since is not None and now - since >= hold:
            return
        if now > deadline:
            top = subprocess.run(
                ["/bin/ps", "-Ao", "pcpu,comm", "-r"], capture_output=True, text=True, check=False
            ).stdout.splitlines()[:12]
            raise SystemExit("host never got quiet; busiest processes:\n" + "\n".join(top))
        time.sleep(30)


def _host_facts() -> dict[str, Any]:
    """The machine the numbers come from."""
    cpus = os.cpu_count() or 1
    try:
        chip = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        chip = sys.platform
    sys.stdout.write(f"host {chip}, {cpus} CPUs\n")
    return {"machine": f"{chip}, {cpus} CPUs"}


def _measure(t: Tour, user_class: str, hold: float) -> dict[str, Any]:
    """Run one user class ``LOCUST_REPEATS`` times on a quiet host; keep the last run.

    The first runs warm the SQLite file cache. Each run records the host's load average and
    CPU idle right before it starts and right after Locust exits.
    """
    runs = []
    for i in range(LOCUST_REPEATS):
        _wait_for_quiet(hold if i == 0 else 30.0)
        start = _host_sample()
        figures = _run_locust(t, user_class, f"{user_class}-{i + 1}")
        figures["host"] = {"start": start, "end": _host_sample()}
        sys.stdout.write(f"locust {user_class} run {i + 1}: {json.dumps(figures)}\n")
        runs.append(figures)
    return runs[-1]


def _run_locust(t: Tour, user_class: str, label: str) -> dict[str, Any]:
    """Measure one user class of scripts/demo_tour_locust.py against the 1.2 M-row app."""
    locust = shutil.which("locust")
    if locust is None:
        raise SystemExit("locust is not installed: uv sync --extra loadtest")
    out = t.work / f"locust-{label}.json"
    # An idle Mac can sleep mid-run: the clock stops and the run measures seconds, not 30.
    awake = ["/usr/bin/caffeinate", "-i"] if Path("/usr/bin/caffeinate").exists() else []
    run = subprocess.run(  # noqa: S603 - fixed argv
        [
            *awake,
            locust,
            *("-f", "scripts/demo_tour_locust.py", "--headless", "--only-summary"),
            *("-u", str(LOCUST_USERS), "-r", str(LOCUST_USERS), "-t", "300s"),
            *("--host", t.apps.url("scale", for_browser=False), user_class),
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "LOADTEST_USER": "alice",
            "LOADTEST_PASSWORD": "secret123",
            "E2E_SCALABILITY_SCALE": str(SCALE),
            "TOUR_USERS": str(LOCUST_USERS),
            "TOUR_SECONDS": str(LOCUST_SECONDS),
            "TOUR_OUT": str(out),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if not out.exists():
        raise RuntimeError(f"locust {user_class} failed:\n{run.stderr[-2000:]}")
    figures: dict[str, Any] = json.loads(out.read_text())
    sys.stdout.write(f"locust {user_class}: {json.dumps(figures['total'])}\n")
    return figures


def _locust_table(title: str, figures: dict[str, Any]) -> str:
    """Per-endpoint rows of one measurement, then its total."""
    lines = [
        f"{title:<14}{'requests':>10}{'fails':>7}{'req/s':>8}{'median':>11}{'p95':>11}{'p99':>11}"
    ]
    rows = [*figures["endpoints"].items(), ("all", figures["total"])]
    if "without_search" in figures:
        rows.append(("list+detail", figures["without_search"]))
    for name, row in rows:
        lines.append(
            f"  {name:<12}{row['requests']:>10}{row['failures']:>7}{row['rps']:>8.0f}"
            f"{row['p50']:>8.0f} ms{row['p95']:>8.0f} ms{row['p99']:>8.0f} ms"
        )
    return "\n".join(lines)


def _locust_card(title: str, figures: dict[str, Any]) -> str:
    total = figures["total"]
    ops = ", ".join(
        f"{name} {row['p50']:.0f}/{row['p95']:.0f}" for name, row in figures["endpoints"].items()
    )
    browse = figures.get("without_search")
    split = (
        f" Without search (list + detail): median {browse['p50']:.0f} ms, p95 {browse['p95']:.0f} ms."
        if browse
        else ""
    )
    host = figures["host"]
    return (
        f'<div class="card"><b>{total["rps"]:.0f} req/s</b><span>{title}: median '
        f"{total['p50']:.0f} ms, p95 {total['p95']:.0f} ms, p99 {total['p99']:.0f} ms, "
        f"{total['failures']} of {total['requests']} failed. Median/p95 ms: {ops}.{split} "
        f"Host load/idle: {_host_text(host['start'])} before, {_host_text(host['end'])} after"
        "</span></div>"
    )


def _host_text(sample: dict[str, float | None]) -> str:
    idle = sample["idle"]
    return f"{sample['load']:.1f}/{idle:.0f}%" if idle is not None else f"{sample['load']:.1f}"


def _logfire_spans(log: Path, request: str) -> str:
    """The span tree Logfire printed for the last ``request``, as escaped HTML lines."""
    lines = log.read_text(errors="replace").splitlines()
    top = re.compile(rf"^\d\d:\d\d:\d\d\.\d+ {re.escape(request)}$")
    start = max(i for i, line in enumerate(lines) if top.match(line))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not re.match(r"^\d\d:\d\d:\d\d\.\d+\s{3,}", line):
            break
        block.append(line)
    out = []
    for line in block[:14]:
        line = re.sub(r"/\S*/(full_demo\.db)", r"\1", line)  # noqa: PLW2901
        stamp, _, rest = line.partition(" ")
        out.append(f'<span class="dim">{html.escape(stamp)}</span> {html.escape(rest)}')
    return "\n".join(out)


def _grid_tiles(crops: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """The twelve crops that stay legible as small tiles (thin strips and wide forms do not)."""
    return [(name, path) for name, path in crops if not name.startswith(GRID_SKIP)][:12]


def _tile_fit(path: Path) -> str:
    """Fill a montage tile with a crop, unless it is a thin strip that would blow up."""
    with Image.open(path) as img:
        return "contain;object-position:center" if img.width > 6 * img.height else "cover"


def _widget_crops(t: Tour) -> list[tuple[str, Path]]:
    """Crop one PNG per distinct component from the ERP and plugin apps."""
    crops: list[tuple[str, Path]] = []

    def crop(name: str, locator: Locator, pad: int = 8, max_height: float = 520) -> None:
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box()
        if box is None:
            return
        path = t.work / f"widget-{len(crops):02d}.png"
        page = locator.page
        page.wait_for_timeout(150)
        page.screenshot(
            path=path,
            clip={
                "x": max(box["x"] - pad, 0),
                "y": max(box["y"] - pad, 0),
                "width": box["width"] + 2 * pad,
                "height": min(box["height"] + 2 * pad, max_height),
            },
        )
        crops.append((name, path))

    # The sticky save bar would cover the fieldsets near the bottom of a form.
    no_sticky_bar = '[data-testid="form-actions"] { display: none !important; }'
    base = t.apps.url("erp")
    page = _context(t.browser).new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice?filter_status=Sent")
    table = page.get_by_test_id("list-table")
    crop("Status pills from an Enum", table.get_by_test_id("list-row").first.locator(".."), 0)
    crop("Filter sidebar from list_filter", page.get_by_test_id("filter-sidebar"), max_height=400)
    crop("Date range with quick ranges", page.get_by_test_id("filter-date_due"))
    page.goto(base + "/admin/invoice")
    rows = page.get_by_test_id("list-row")
    for i in range(3):
        rows.nth(i).get_by_test_id("bulk-checkbox").check()
    crop("Bulk actions from @action(bulk=True)", page.get_by_test_id("bulk-bar"))
    crop("Pagination and page size", page.get_by_test_id("pagination-info").locator(".."))
    page.goto(base + "/admin/invoice/1")
    crop("Detail page with custom actions", page.get_by_test_id("detail-fields").locator(".."))
    page.goto(base + "/admin/invoice/1/edit")
    page.add_style_tag(content=no_sticky_bar)
    crop("Inline related rows", page.get_by_test_id("inline-invoiceitem"))
    page.goto(base + "/admin/fieldshowcase/create")
    page.add_style_tag(content=no_sticky_bar)
    crop("Enum select, multi-select, number inputs", page.get_by_test_id("fieldset-attributes"))
    crop("File and image upload", page.get_by_test_id("fieldset-media"))
    page.get_by_test_id("autocomplete-category_id").click()
    page.wait_for_timeout(500)
    crop("Foreign-key autocomplete with “+” popup", page.get_by_test_id("fieldset-relations"))
    page.goto(base + "/admin/invoice")
    page.keyboard.press("?")
    expect(page.get_by_test_id("shortcuts-overlay")).to_be_visible()
    crop("Keyboard shortcuts", page.get_by_test_id("shortcuts-overlay"))
    page.keyboard.press("Escape")
    page.get_by_test_id("list-row").nth(1).get_by_test_id("row-delete-btn").click()
    dialog = page.get_by_test_id("dialog-confirm-delete")
    expect(dialog).to_be_visible()
    crop("Confirm dialogs", dialog)
    page.keyboard.press("Escape")
    page.get_by_test_id("nav-pin-invoice").click()
    expect(page.get_by_test_id("nav-pinned")).to_be_visible()
    crop("Grouped sidebar with pins", page.get_by_test_id("sidebar"), 0, max_height=420)
    _ensure_group(page, base)  # the matrix needs a group to show
    page.goto(base + "/admin/permissions-matrix/")
    crop("Permissions matrix", page.get_by_test_id("pmatrix-table"), max_height=420)
    page.context.close()

    page = _context(t.browser).new_page()
    _sign_in(page, t.apps.url("dashboard"), "alice", "secret123")
    expect(page.get_by_test_id("widget-loading")).to_have_count(0, timeout=15000)
    crop("Stat widget", page.get_by_test_id("widget-stat-orders-revenue"), max_height=200)
    crop("Chart widget", page.get_by_test_id("widget-chart-orders-by-month"))
    page.context.close()

    page = _context(t.browser).new_page()
    _sign_in(page, t.apps.url("tasks"), "alice", "secret123")
    page.goto(t.apps.url("tasks") + "/admin/tasks/")
    crop("Task queues", page.get_by_test_id("tasks-dashboard"))
    page.context.close()
    return crops


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


# ── Docs screenshots ────────────────────────────────────────────────────────────────


def render_screenshots(browser: Browser, base: str) -> None:
    """Refresh the docs/assets/demo tour and the ERP feature shots of docs/demo.md."""
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
    page.goto(
        base + "/admin/invoice?search=INV-1&filter_status=Sent&sort_by=date_due&sort_direction=desc"
    )
    _save(page, SHOTS_DIR / "list-search-filters.png")

    page.goto(base + "/admin/invoice")
    rows = page.get_by_test_id("list-row")
    for i in range(3):
        rows.nth(i).get_by_test_id("bulk-checkbox").check()
    expect(page.get_by_test_id("bulk-bar")).to_be_visible()
    page.get_by_test_id("bulk-action-select").select_option(label="Mark paid")
    _save(page, SHOTS_DIR / "bulk-actions.png")

    page.goto(base + "/admin/invoice/1")
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    _save(page, DEMO_DIR / "detail.png")
    page.get_by_test_id("detail-edit-link").click()
    expect(page.get_by_test_id("model-form")).to_be_visible()
    page.get_by_test_id("inline-invoiceitem").scroll_into_view_if_needed()
    _save(page, SHOTS_DIR / "form-inlines.png")
    page.goto(base + "/admin/invoice/create")
    expect(page.get_by_test_id("model-form")).to_be_visible()
    _save(page, DEMO_DIR / "create.png")

    _ensure_group(page, base)
    page.goto(base + "/admin/permissions-matrix/")
    expect(page.get_by_test_id("pmatrix-table")).to_be_visible()
    _tick_matrix(page)
    _save(page, SHOTS_DIR / "permission-matrix.png")
    page.goto(base + "/admin/erp/profit-loss")
    _save(page, SHOTS_DIR / "profit-loss.png")
    ctx.close()

    ctx = _context(browser)
    page = ctx.new_page()
    _sign_in(page, base, "demo_ro", "demo_ro")
    page.goto(base + "/admin/invoice")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    _save(page, SHOTS_DIR / "read-only-list.png")
    ctx.close()

    ctx = _context(browser, dark=True)
    page = ctx.new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    _save(page, DEMO_DIR / "list-dark.png")
    ctx.close()

    ctx = _context(browser, phone=True)
    page = ctx.new_page()
    _sign_in(page, base)
    page.goto(base + "/admin/invoice")
    _save(page, DEMO_DIR / "list-mobile.png")
    ctx.close()


def render_palette_records(browser: Browser, base: str) -> None:
    """The command palette finding a record (``palette_search=True``) for the navigation guide."""
    ctx = _context(browser)
    page = ctx.new_page()
    _sign_in(page, base, "alice", "secret123")
    page.keyboard.press("ControlOrMeta+k")
    page.get_by_test_id("palette-input").fill("1042")
    records = page.get_by_role("group", name="Records")
    expect(records.get_by_test_id("palette-result").filter(has_text="ORD-1042")).to_be_visible()
    _save(page, SHOTS_DIR / "command-palette-records.png")
    ctx.close()


# ── Encoding ────────────────────────────────────────────────────────────────────────


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
    *,
    screenshots: bool,
    video: bool,
    scenes: Sequence[str] | None = None,
    frames_dir: Path | None = None,
    browser_ws: str | None = None,
    browser_host: str | None = None,
) -> None:
    """Boot the apps, render the scenes into a reel and encode it (unless ``scenes``)."""
    chosen = [(name, fn) for name, fn in SCENES if scenes is None or name in scenes]
    with (
        tempfile.TemporaryDirectory(prefix="hyperadmin-tour-") as tmp,
        ExitStack() as stack,
        sync_playwright() as pw,
    ):
        work = Path(tmp)
        if browser_ws:
            # A remote (Linux) browser: en-US date and number inputs on any host OS.
            browser = pw.chromium.connect(browser_ws)
        else:
            # On macOS date and number inputs follow the system locale, whatever --lang says.
            browser = pw.chromium.launch(args=["--lang=en-US"])
            browser_host = None
        apps = Apps(stack, work, browser_host=browser_host)
        reel = Reel(frames_dir or work, save_shots=screenshots)
        tour = Tour(pw, browser, apps, reel, work)
        if screenshots and scenes is None:
            render_screenshots(browser, apps.url("erp"))
            render_palette_records(browser, apps.url("palette"))
        if video or scenes is not None:
            reel.workdir.mkdir(parents=True, exist_ok=True)
            for name, scene in chosen:
                sys.stdout.write(f"── {name}\n")
                scene(tour)
            sys.stdout.write(f"reel length {reel.length:.1f}s, {len(reel.frames)} frames\n")
            if scenes is None and video:
                encode(reel, DEMO_DIR)
        browser.close()
        if tour._local is not None:
            tour._local.close()


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments and render the tour."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--no-video", action="store_true", help="only render the screenshots")
    parser.add_argument("--no-screenshots", action="store_true", help="only render the video")
    parser.add_argument("--list-scenes", action="store_true", help="print the scene names")
    parser.add_argument(
        "--scenes",
        help="comma-separated scene names to render into --frames, without encoding",
    )
    parser.add_argument("--frames", type=Path, help="keep the video frames in this directory")
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
    if args.list_scenes:
        for name, scene in SCENES:
            sys.stdout.write(f"{name:12} {(scene.__doc__ or '').splitlines()[0]}\n")
        return
    scenes = [s.strip() for s in args.scenes.split(",")] if args.scenes else None
    unknown = set(scenes or []) - {name for name, _ in SCENES}
    if unknown:
        parser.error(f"unknown scenes: {', '.join(sorted(unknown))}")
    render(
        screenshots=not args.no_screenshots,
        video=not args.no_video,
        scenes=scenes,
        frames_dir=args.frames,
        browser_ws=args.browser_ws,
        browser_host=args.browser_host,
    )


if __name__ == "__main__":
    main()
