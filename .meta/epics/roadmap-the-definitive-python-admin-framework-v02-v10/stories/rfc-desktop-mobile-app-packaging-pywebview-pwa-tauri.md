---
type: story
id: mwejjbPMLIS_
title: "RFC: Desktop & mobile app packaging (PyWebView, PWA, Tauri)"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - rfc
estimate: null
epic_ref:
  id: EGeVWNoBWlNq
github:
  issue_number: 272
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:be15db12065d5adf95cbac7166e8d3cb18746268a67fd510439d6a0b9bbfcfe6
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T09:03:09Z
updated_at: 2026-03-27T09:03:09Z
---

## Summary

Package HyperAdmin as a desktop app and mobile-friendly PWA, enabling local-only admin panels, offline-capable dashboards, and single-binary distribution.

Parent: #270

## Motivation

HyperAdmin is a server-rendered FastAPI app — but many use cases benefit from desktop/mobile packaging:
- **Local admin tool** — manage a local SQLite database without deploying a server
- **System tray app** — always-running admin server accessible from the taskbar
- **Mobile access** — responsive admin on phones/tablets via PWA
- **Single-binary distribution** — ship a self-contained admin to non-technical users

## Desktop Options (Ranked by Feasibility)

### 1. PyWebView (Recommended)

Lightweight Python library that creates a native OS window with an embedded web browser component. ~5-15 MB footprint vs. 150+ MB for Electron.

```python
# desktop.py — ~30 lines total
import threading, webview, uvicorn
from myapp import app

threading.Thread(target=uvicorn.run, args=(app,), kwargs={"port": 8421}, daemon=True).start()
webview.create_window("HyperAdmin", "http://127.0.0.1:8421")
webview.start()
```

**Pros:** Pure Python, no second runtime, tiny footprint, mature (9+ years, 4.5k+ stars)
**Cons:** Rendering engine varies by OS (WebKit/Edge), no built-in auto-updater

### 2. Tauri v2 with Python Sidecar

Rust-based app shell (~3-8 MB) using OS webview. Ships a PyInstaller-frozen FastAPI binary as a "sidecar." Built-in auto-updater, system tray, native menus.

**Pros:** Smallest shell, native features, code signing pipeline
**Cons:** Requires Rust toolchain for builds, two-process architecture

### 3. Electron (Not Recommended)

150-300 MB minimum. Overkill for server-rendered HTML. Only if team already has Electron infra.

### 4. Briefcase (BeeWare)

Cross-platform packaging including mobile. Mobile support still "early access." Less battle-tested than PyWebView for desktop.

## Mobile Options (Ranked)

### 1. Progressive Web App (Recommended)

Minimal effort, maximum reach. HyperAdmin would need:

- **`manifest.json`** — app name, icons (192px + 512px), `display: "standalone"`
- **Service Worker** — network-first caching for app shell
- **Responsive CSS** — collapsible sidebar, mobile tables, touch-friendly targets
- **Meta tags** — `<meta name="theme-color">`, Apple PWA tags

**Why PWA wins:** Zero app store friction, no separate codebase, admin panels inherently need connectivity. iOS PWA support has improved significantly (push notifications since iOS 16.4+).

### 2. Capacitor/Ionic

Wraps web app in native WebView for app store distribution. Only makes sense if app store presence is required AND the admin connects to a remote server.

### 3. BeeWare/Toga Mobile

Too immature today. Revisit later.

## Single-Binary Distribution

| Tool | Output | Size | Startup | Recommendation |
|------|--------|------|---------|----------------|
| **PyInstaller** `--onedir` | Directory bundle | 30-80 MB | Fast | **Primary choice** |
| **PyInstaller** `--onefile` | Single executable | 30-80 MB | 3-8s cold start | Convenience option |
| **Nuitka** | Compiled binary | Smaller | Faster | Evaluate if perf matters |
| **Docker** | Container image | Variable | Fast | Server deployments |

## Key Challenges & Solutions

### Auth in Local Mode

| Scenario | Approach |
|----------|----------|
| Single-user desktop + SQLite | **Skip auth** — OS login is sufficient |
| Desktop + remote DB | **Keep full auth** — multiple users may exist |
| Default | Auto-detect: skip auth for `sqlite://` URLs, require auth for remote URLs |

### Port Conflicts
Use a random available port or configurable default (e.g., 8421). PyWebView handles this naturally.

### System Tray
`pystray` library for PyWebView. Tauri has built-in support. Pattern: minimize to tray, click to reopen, right-click for quick actions.

### Local-Remote Data Sync
**Avoid.** Treat local and remote as separate deployment modes. If needed, one-way export/import (dump SQLite → import to Postgres) is sufficient. True bidirectional sync (CRDTs/event sourcing) is massive complexity for marginal admin benefit.

## Recommended Implementation Plan

### Phase A: PWA (near-zero effort)
- Add `manifest.json` + minimal service worker + responsive CSS tweaks
- ~100-200 lines of new code, no native toolchain needed

### Phase B: Desktop wrapper (low effort)
- Add `desktop.py` entry point (PyWebView + Uvicorn in thread)
- Package with PyInstaller `--onedir` for macOS/Windows/Linux
- Optional: `pystray` for system tray
- ~30-50 lines of Python

### Phase C: Polish (if demand warrants)
- Migrate to Tauri v2 for auto-updates, code signing, native menus
- Evaluate Nuitka for faster startup
- App store distribution via Capacitor (if needed)

## What to Avoid

- **Electron** — too heavy for server-rendered admin
- **BeeWare mobile** — too immature
- **Textual TUI** — that's a rewrite, not packaging
- **Local-remote sync** — enormous complexity, marginal benefit

## Open Questions

- [ ] Should the desktop wrapper be a separate package (`hyperadmin-desktop`) or a built-in entry point?
- [ ] Code signing: Apple Developer ($99/yr) + Windows EV cert ($200-400/yr) — worth it for initial release?
- [ ] System tray: always-on server vs. launch-on-demand?
- [ ] Auto-update mechanism for PyWebView builds (pyupdater? HTTP version check?)

---
https://claude.ai/code/session_01XktRz2PFThVGgPMoUmaEjc
