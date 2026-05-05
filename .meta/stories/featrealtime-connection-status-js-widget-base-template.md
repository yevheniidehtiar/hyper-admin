---
type: story
title: "feat(realtime): connection-status JS widget in _base.html (auto-reconnect + backoff)"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:realtime
  - area:ui
estimate: null
epic_ref: null
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
A small navbar dot (green / yellow / red) tells the operator that the real-time channel is healthy. The JS opens both SSE and WS on page load, exposes `window.__rt.state` for E2E assertions, and reconnects with exponential backoff + jitter on drop. No business payload.

## Scenarios

**Scenario: dot turns green when both transports are open**
  Given an authenticated admin page
  When  the page loads and both connections are established
  Then  `window.__rt.state` reads `"connected"`
  And   the navbar dot has `data-testid="realtime-status"` and class `is-connected`

**Scenario: dot turns yellow on disconnect**
  Given a connected page
  When  the network drops or the server restarts
  Then  `window.__rt.state` reads `"reconnecting"` within 1 s
  And   the dot has class `is-reconnecting`

**Scenario: dot returns to green after reconnect**
  Given a reconnecting page
  When  the server is reachable again
  Then  `window.__rt.state` reads `"connected"` within 5 s
  And   the dot has class `is-connected`
  And   the page is NOT reloaded

**Scenario: backoff caps at 10 s with jitter**
  Given repeated failed reconnect attempts
  When  the 6th attempt is scheduled
  Then  the delay is between 7 s and 13 s (10 s cap ± jitter)

**Scenario: widget is absent when realtime is disabled**
  Given an `Admin()` constructed without a `realtime=` kwarg
  When  the page loads
  Then  no `realtime-status.js` script tag is in the document
  And   no `[data-testid="realtime-status"]` element exists

## Acceptance Criteria
- [ ] `src/hyperadmin/static/js/realtime-status.js` (new) — vanilla JS, no framework deps
- [ ] Status element added to `templates/_navbar.html` with `data-testid="realtime-status"`
- [ ] Script tag added to `templates/_base.html`, conditional on `realtime_enabled` template global
- [ ] `realtime_enabled` global set in `Admin.mount()` from `self.realtime is not None`
- [ ] Reconnect: 250 ms × 2ⁿ + ±30 % jitter, capped at 10 s
- [ ] Tested via Playwright `page.evaluate(() => window.__rt.state)` — see E2E story

## Files Likely Affected
- `src/hyperadmin/static/js/realtime-status.js` (new)
- `src/hyperadmin/templates/_base.html`
- `src/hyperadmin/templates/_navbar.html`
- `src/hyperadmin/core/app.py` (one new template global)

## Dependencies
Blocked by: SSE endpoint story, WS endpoint story
