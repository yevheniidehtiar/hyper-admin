---
type: story
id: JmyfP0svIUXY
title: "test(e2e): Presence banner — two sessions editing same record"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - area:presence
estimate: null
epic_ref: null
github:
  issue_number: 329
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d3f2a89f8fbfe52002e2ceb42ee3aa52e85e25a788dda347bb6c9e1747f14671
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:01:59Z
updated_at: 2026-03-29T07:01:59Z
---

## Context
End-to-end verification of the full presence pipeline: two admins open the same edit form; each sees the other in the presence banner; when one leaves, they disappear after TTL.

## Acceptance Criteria
- [ ] Two Playwright sessions open the same record edit form
- [ ] Session A's banner shows Session B's username with "editing" mode
- [ ] Session B's banner shows Session A's username
- [ ] Session B closes tab → Session A's banner clears after heartbeat TTL (~12s, configurable)
- [ ] No console errors in either session
- [ ] Tests in `tests/e2e/test_presence.py`

## Files Likely Affected
- `tests/e2e/test_presence.py` (new)

## Dependencies
Depends on: #328

## Notes for Implementer
Use `page.wait_for_timeout()` to wait for TTL expiry. Two contexts must share the same server instance. Test must handle async timing carefully.
