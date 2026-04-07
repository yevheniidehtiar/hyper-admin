---
type: story
id: JSnUsUcWNc_N
title: "test(realtime): RealtimeEvent dataclass unit tests"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 308
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:635e04d6c1ad7667faba0c7986843b0e673f6227b91e9c68cfc83a7b2ccc83e3
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:36Z
updated_at: 2026-03-29T06:58:36Z
---

## Context
RealtimeEvent is the message envelope used to communicate CRUD changes over WebSocket. It carries enough context to render the correct HTML fragment.

## Acceptance Criteria
- [ ] Test: `RealtimeEvent` has fields: `model_name`, `pk`, `action` (enum), `html_fragment` (str | None)
- [ ] Test: `RealtimeAction` enum has `created`, `updated`, `deleted` values
- [ ] Test: `to_bytes()` serializes to JSON bytes
- [ ] Test: `from_bytes()` deserializes correctly
- [ ] Tests in `tests/unit/test_realtime_event.py`

## Files Likely Affected
- `tests/unit/test_realtime_event.py` (new)

## Dependencies
Depends on: #303

## Notes for Implementer
Tests must FAIL before T8.
