---
type: story
id: GmWCokj4PqVc
title: "feat(presence): Heartbeat handler + presence broadcasts in ConnectionManager"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:presence
estimate: null
epic_ref:
  id: Y-nzspSqDFUM
github:
  issue_number: 327
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ec01b27a62e1ac5295d5e60ecf9c569a322be8bcb2dcc7ca61b779b1de4f0a29
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:01:37Z
updated_at: 2026-03-29T07:01:37Z
---

## Context
Extends the WebSocket ConnectionManager to handle presence heartbeats and broadcast presence HTML fragments to all connected viewers of the same record.

## Acceptance Criteria
- [ ] `ConnectionManager` parses incoming JSON WS messages and routes presence actions to `PresenceBackend`
- [ ] On presence update: renders `presence_banner.html` fragment and broadcasts as `hx-swap-oob` to channel subscribers
- [ ] On client disconnect: `presence_backend.remove_presence()` called, updated banner broadcast
- [ ] `presence_backend` kwarg added to `Admin.__init__()` (default: `InMemoryPresence()`)
- [ ] All P5 tests pass

## Files Likely Affected
- `src/hyperadmin/views/websocket.py`
- `src/hyperadmin/core/app.py`

## Dependencies
Depends on: #326

## Notes for Implementer
Reuse the same WS connection from T6 — do NOT open a second WebSocket. Presence messages and notification messages share one connection, differentiated by message `type` field.
