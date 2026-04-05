---
type: story
id: WaUMSidNXi-Y
title: "test(e2e): Live notifications — two browser sessions on same list view"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 313
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0aa793eb29b4d6a5330bfc671a58224bd42c5a710c4efe17c78598883c5bbb23
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:59:24Z
updated_at: 2026-03-29T06:59:24Z
---

## Context
End-to-end verification that the full notification pipeline works: adapter emits event → pubsub broadcasts → WebSocket delivers → HTMX swaps HTML in browser.

## Acceptance Criteria
- [ ] Two Playwright browser contexts open `/admin/{model}/` list view
- [ ] Session A creates a new record → Session B sees toast notification + new row appears without page reload
- [ ] Session A deletes a row → Session B's row disappears without reload
- [ ] Session A updates a row → Session B's row reflects updated values
- [ ] No console errors in either session
- [ ] Tests in `tests/e2e/test_realtime_notifications.py`

## Files Likely Affected
- `tests/e2e/test_realtime_notifications.py` (new)

## Dependencies
Depends on: #312

## Notes for Implementer
Use `page.wait_for_selector()` or `expect(locator).to_be_visible()` for assertions. Two contexts must share the same server instance. Follow existing E2E test patterns in `tests/e2e/`.
