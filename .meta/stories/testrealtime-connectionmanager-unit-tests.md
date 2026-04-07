---
type: story
id: 72lX_h3zC2v-
title: "test(realtime): ConnectionManager unit tests"
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
  issue_number: 306
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b343de975604d4b412517561679b43fd441b92d1aea53a25bb98d396b0243594
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:18Z
updated_at: 2026-03-29T06:58:18Z
---

## Context
ConnectionManager is the central hub that tracks active WebSocket connections per channel and broadcasts HTML fragments to subscribers. Must handle concurrent connections gracefully.

## Acceptance Criteria
- [ ] Test: register/unregister WebSocket connections by channel key (format: `model:list`, `model:pk`)
- [ ] Test: broadcast bytes reaches all subscribers of a channel, not others
- [ ] Test: `send_html_fragment(channel, html)` helper encodes and broadcasts correctly
- [ ] Test: graceful handling of client disconnect during broadcast (no exception leaks)
- [ ] Test: no connection leak after client disconnects
- [ ] Tests in `tests/unit/test_connection_manager.py`

## Files Likely Affected
- `tests/unit/test_connection_manager.py` (new)

## Dependencies
Depends on: #303

## Notes for Implementer
Mock the WebSocket object. Tests must FAIL before T6.
