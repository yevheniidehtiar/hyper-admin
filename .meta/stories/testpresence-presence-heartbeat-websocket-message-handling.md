---
type: story
id: OxqHNv402iYT
title: "test(presence): Presence heartbeat WebSocket message handling"
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
  issue_number: 326
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ac40ed17fa848c018df34250197ae4dccba728c10fca609ac42a07c77e5de302
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:01:28Z
updated_at: 2026-03-29T07:01:28Z
---

## Context
The browser sends periodic heartbeat messages over the existing WebSocket connection to declare its presence. The server updates the presence store and broadcasts the updated banner HTML to all viewers of the same record.

## Acceptance Criteria
- [ ] Test: `ConnectionManager` handles incoming WS JSON `{action: "viewing"|"editing", model: str, pk: str, user: str}` by calling `presence_backend.set_presence()`
- [ ] Test: on client disconnect, `presence_backend.remove_presence()` is called
- [ ] Test: after presence update, updated presence HTML fragment is broadcast to all connections on that channel
- [ ] Tests mock both `PresenceBackend` and WebSocket
- [ ] Tests in `tests/unit/test_presence_heartbeat.py`

## Files Likely Affected
- `tests/unit/test_presence_heartbeat.py` (new)

## Dependencies
Depends on: T6 (must be merged from v0.6.2, issue #307), #323

## Notes for Implementer
Tests must FAIL before P6. This is the bridge between the WS infrastructure (T6) and the presence system (P2).
