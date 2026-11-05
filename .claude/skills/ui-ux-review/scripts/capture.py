"""Capture HyperAdmin screenshots across devices and themes, plus automated UX checks.

Usage (app already running, e.g. ``uv run examples/full-demo/main.py``)::

    uv run python .claude/skills/ui-ux-review/scripts/capture.py \
        --base-url http://127.0.0.1:8000 --login alice:secret123 --out ux-review/run-1

Pages come from ``--paths`` or, by default, are discovered from the sidebar: every
model list, plus the first row's detail and edit page and the create page.

Output in ``--out``:
  ``<page>/<device>-<theme>.png``  full-page screenshots
  ``findings.json``                automated findings per page / device / theme
  ``index.md``                     one table per page, the screenshot paths and finding counts
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


@dataclass(frozen=True)
class Device:
    name: str
    width: int
    height: int
    scale: float
    mobile: bool
    touch: bool


DEVICES: dict[str, Device] = {
    d.name: d
    for d in (
        Device("phone-small", 360, 740, 2, True, True),  # Android compact (Galaxy S-class)
        Device("phone", 393, 852, 2, True, True),  # iPhone 15 / 16
        Device("phone-landscape", 852, 393, 2, True, True),
        Device("tablet", 768, 1024, 2, True, True),  # iPad mini portrait
        Device("tablet-landscape", 1180, 820, 2, True, True),  # iPad Air landscape
        Device("laptop", 1280, 800, 2, False, False),
        Device("desktop", 1920, 1080, 1, False, False),
    )
}
DEFAULT_DEVICES = "phone-small,phone,tablet,tablet-landscape,laptop,desktop"

# Runs inside the page; returns a list of findings for the current viewport.
CHECKS_JS = r"""
({touch}) => {
  const out = [];
  const byKey = new Map();
  const vw = document.documentElement.clientWidth;
  const add = (rule, severity, el, detail) => {
    let sel = '';
    // One finding per rule + component: repeated rows count, they are not listed.
    const key = rule + '|' + (el ? (el.getAttribute('data-testid') || el.tagName + '.' + el.className) : '');
    if (byKey.has(key)) { byKey.get(key).count++; return; }
    if (el) {
      const tid = el.getAttribute && el.getAttribute('data-testid');
      sel = tid ? `[data-testid="${tid}"]` : el.tagName.toLowerCase() +
        (el.id ? '#' + el.id : '') +
        (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
      const text = (el.innerText || el.getAttribute('aria-label') || el.value || '').trim();
      if (text) sel += ` "${text.slice(0, 40)}"`;
    }
    const item = {rule, severity, element: sel, detail, count: 1};
    byKey.set(key, item);
    out.push(item);
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    // Visually hidden on purpose (sr-only, skip links, closed drawers) is not a defect.
    if (r.width <= 1 || r.height <= 1 || r.right <= 0 || r.left >= vw) return false;
    if (s.clipPath !== 'none' || (s.clip && s.clip !== 'auto')) return false;
    return s.visibility !== 'hidden' && s.display !== 'none'
      && s.opacity !== '0' && !el.closest('[inert],[aria-hidden="true"]');
  };
  // Small control inside a larger clickable row/card: the container is the target.
  const inBigTarget = (el, min) => {
    for (let p = el.parentElement, i = 0; p && i < 4; p = p.parentElement, i++) {
      const r = p.getBoundingClientRect();
      if (getComputedStyle(p).cursor === 'pointer' && r.height >= min && r.width >= min) return true;
    }
    return false;
  };

  // 1. Horizontal page scroll.
  const sw = document.documentElement.scrollWidth;
  if (sw > vw + 1) add('horizontal-scroll', 'high', null, `page is ${sw}px wide in a ${vw}px viewport`);

  // 2. Elements sticking out of the viewport (skip anything inside a scroll container).
  const inScroller = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden') return true;
    }
    return false;
  };
  let overflowCount = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (overflowCount >= 10 || !visible(el)) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !inScroller(el)) {
      add('off-screen', 'high', el, `spans ${Math.round(r.left)}..${Math.round(r.right)}px, viewport ${vw}px`);
      overflowCount++;
    }
  }

  // 3. Tap targets: WCAG 2.5.8 minimum 24px; 44px on touch devices (Apple HIG / WCAG 2.5.5).
  const interactive = 'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=link],[role=tab],[role=checkbox],summary';
  const minTarget = touch ? 44 : 24;
  let smallCount = 0;
  for (const el of document.querySelectorAll(interactive)) {
    if (!visible(el) || smallCount >= 15) continue;
    const r = el.getBoundingClientRect();
    // Inline text links inside a sentence are exempt from 2.5.8.
    if (el.tagName === 'A' && getComputedStyle(el).display === 'inline' && el.parentElement &&
        (el.parentElement.innerText || '').trim().length > (el.innerText || '').trim().length + 20) continue;
    if ((r.width < minTarget || r.height < minTarget) && !inBigTarget(el, minTarget)) {
      const sev = (r.width < 24 || r.height < 24) ? 'high' : 'medium';
      add('tap-target', sev, el, `${Math.round(r.width)}x${Math.round(r.height)}px < ${minTarget}px`);
      smallCount++;
    }
  }

  // 4. Text contrast (WCAG 1.4.3): 4.5:1 normal, 3:1 for large/bold text.
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lum = ({r, g, b}) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const bgOf = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.backgroundImage && s.backgroundImage !== 'none') return null;  // gradient/image: skip
      const c = parse(s.backgroundColor);
      if (c && c.a >= 0.95) return c;
    }
    return parse(getComputedStyle(document.body).backgroundColor) || {r: 255, g: 255, b: 255, a: 1};
  };
  let lowCount = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const el = walker.currentNode.parentElement;
    if (!el || seen.has(el) || !walker.currentNode.textContent.trim()) continue;
    if (!visible(el)) continue;
    seen.add(el);
    if (el.closest('[disabled],[aria-disabled="true"]')) continue;
    const s = getComputedStyle(el);
    const fg = parse(s.color), bg = bgOf(el);
    if (!fg || !bg || fg.a < 0.5) continue;
    const l1 = lum(fg), l2 = lum(bg);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(s.fontSize), bold = parseInt(s.fontWeight, 10) >= 700;
    const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5;
    if (ratio < need && lowCount < 15) {
      add('contrast', ratio < 3 ? 'high' : 'medium', el, `${ratio.toFixed(2)}:1 < ${need}:1 (${s.color} on rgb(${bg.r},${bg.g},${bg.b}))`);
      lowCount++;
    }
  }

  // 5. Tiny text on small screens.
  if (vw < 768) {
    let tiny = 0;
    for (const el of seen) {
      if (tiny >= 5) break;
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (size < 12) { add('tiny-text', 'medium', el, `${size}px font on a ${vw}px screen`); tiny++; }
    }
  }

  // 6. Clipped text (cut off without an ellipsis).
  let clipped = 0;
  for (const el of seen) {
    if (clipped >= 10) break;
    const s = getComputedStyle(el);
    if ((s.overflow === 'hidden' || s.overflowX === 'hidden') && s.textOverflow !== 'ellipsis' &&
        el.scrollWidth > el.clientWidth + 2) {
      add('clipped-text', 'medium', el, `content ${el.scrollWidth}px in a ${el.clientWidth}px box`);
      clipped++;
    }
  }

  // 7. Missing accessible names.
  for (const el of document.querySelectorAll('img:not([alt])')) if (visible(el)) add('img-alt', 'medium', el, 'image without alt');
  for (const el of document.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]),select,textarea')) {
    if (!visible(el)) continue;
    const named = el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title');
    if (!named) add('unlabelled-control', 'high', el, 'form control has no label');
  }
  for (const el of document.querySelectorAll('button,a[href],[role=button]')) {
    if (!visible(el)) continue;
    const name = (el.innerText || '').trim() || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title') || el.querySelector('img[alt]:not([alt=""]),svg title');
    if (!name) add('unnamed-control', 'high', el, 'button/link has no accessible name');
  }

  // 8. Heading structure.
  const h1 = [...document.querySelectorAll('h1')].filter(visible).length;
  if (h1 !== 1) add('heading-structure', 'low', null, `${h1} visible <h1> on the page (expected 1)`);
  return out;
}
"""


def slug(path: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", path.strip("/")).strip("-")
    return s or "root"


def login(page: Page, base_url: str, creds: str | None) -> None:
    if not creds or "/login" not in page.url:
        return
    user, _, password = creds.partition(":")
    page.get_by_label("Username").fill(user)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name=re.compile("sign in|log in|login", re.I)).click()
    page.wait_for_load_state("networkidle")
    if "/login" in page.url:
        sys.exit(f"login as {user!r} failed at {base_url}")


def discover(page: Page, base_url: str, prefix: str, limit: int) -> list[str]:
    """Collect admin pages from the sidebar, plus one detail/edit/create page per model."""
    page.goto(urljoin(base_url, prefix))
    page.wait_for_load_state("networkidle")
    found: list[str] = [urlparse(page.url).path]
    hrefs = page.get_by_test_id("sidebar").locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    lists = [h for h in dict.fromkeys(hrefs) if h and h.startswith(prefix)]
    for href in lists:
        if len(found) >= limit:
            break
        found.append(href)
        page.goto(urljoin(base_url, href))
        page.wait_for_load_state("networkidle")
        for tid in ("row-link", "row-view-link", "row-edit-link", "create-link"):
            link = page.get_by_test_id(tid).first
            if link.count():
                href = link.get_attribute("href")
                extra = urlparse(urljoin(base_url, href)).path if href else None
                if extra and extra not in found and len(found) < limit:
                    found.append(extra)
    return list(dict.fromkeys(found))


def new_context(browser: Browser, device: Device, theme: str, storage: Any) -> BrowserContext:
    return browser.new_context(
        viewport={"width": device.width, "height": device.height},
        device_scale_factor=device.scale,
        is_mobile=device.mobile,
        has_touch=device.touch,
        color_scheme=theme,  # type: ignore[arg-type]
        reduced_motion="reduce",
        storage_state=storage,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--prefix", default="/admin", help="admin mount path")
    ap.add_argument("--login", help="user:password, used when the app redirects to /login")
    ap.add_argument("--paths", help="comma-separated paths; default: discover from the sidebar")
    ap.add_argument("--max-pages", type=int, default=12)
    ap.add_argument("--devices", default=DEFAULT_DEVICES, help=f"from: {', '.join(DEVICES)}")
    ap.add_argument("--themes", default="light,dark")
    ap.add_argument("--viewport-only", action="store_true", help="above-the-fold shots only")
    ap.add_argument("--out", default=".ux-review/latest")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    devices = [DEVICES[d.strip()] for d in args.devices.split(",")]
    themes = [t.strip() for t in args.themes.split(",")]
    findings: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # Sign in once on a desktop context and reuse the session cookie everywhere.
        ctx = new_context(browser, DEVICES["laptop"], "light", None)
        page = ctx.new_page()
        page.goto(urljoin(args.base_url, args.prefix))
        login(page, args.base_url, args.login)
        storage = ctx.storage_state()
        paths = (
            [p.strip() for p in args.paths.split(",")]
            if args.paths
            else discover(page, args.base_url, args.prefix, args.max_pages)
        )
        ctx.close()

        for device in devices:
            for theme in themes:
                ctx = new_context(browser, device, theme, storage)
                page = ctx.new_page()
                errors: list[str] = []
                page.on("console", lambda m, e=errors: e.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda exc, e=errors: e.append(str(exc)))
                for path in paths:
                    errors.clear()
                    resp = page.goto(urljoin(args.base_url, path))
                    page.wait_for_load_state("networkidle")
                    shot = out / slug(path) / f"{device.name}-{theme}.png"
                    shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shot), full_page=not args.viewport_only)
                    items = page.evaluate(CHECKS_JS, {"touch": device.touch})
                    if resp and resp.status >= 400:
                        items.append({"rule": "http-status", "severity": "high", "element": "", "detail": str(resp.status)})
                    items += [{"rule": "console-error", "severity": "high", "element": "", "detail": e[:200]} for e in errors]
                    findings.append({
                        "path": path, "device": device.name, "theme": theme,
                        "viewport": f"{device.width}x{device.height}",
                        "screenshot": str(shot), "findings": items,
                    })
                    print(f"{device.name:17} {theme:5} {path:40} {len(items):3} findings", flush=True)
                ctx.close()
        browser.close()

    (out / "findings.json").write_text(json.dumps(findings, indent=2))
    lines = [f"# UX capture: {args.base_url}\n"]
    for path in paths:
        lines += [f"\n## `{path}`\n", "| device | theme | findings (high) | screenshot |", "|---|---|---|---|"]
        for f in (x for x in findings if x["path"] == path):
            high = sum(i["severity"] == "high" for i in f["findings"])
            lines.append(f"| {f['device']} | {f['theme']} | {len(f['findings'])} ({high}) | `{f['screenshot']}` |")
    (out / "index.md").write_text("\n".join(lines) + "\n")
    print(f"\n{len(findings)} captures -> {out}/index.md, {out}/findings.json")


if __name__ == "__main__":
    main()
