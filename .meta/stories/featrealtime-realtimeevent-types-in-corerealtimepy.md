---
type: story
id: Ig2rCRL9ihOa
title: "feat(realtime): RealtimeEvent types in core/realtime.py"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:S
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 309
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e3942feab601400086a9d24cf01f074bf4442763349f11c2239d2a94620ad45a
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:58:43Z
updated_at: 2026-03-29T06:58:43Z
---

## Context
Defines the event envelope that flows from adapters through PubSub to connected browsers.

## Acceptance Criteria
- [ ] `RealtimeAction` enum (`created`, `updated`, `deleted`) added to `src/hyperadmin/core/realtime.py`
- [ ] `RealtimeEvent` dataclass with `model_name: str`, `pk: Any`, `action: RealtimeAction`, `html_fragment: str | None`
- [ ] `to_bytes() -> bytes` and `from_bytes(data: bytes) -> RealtimeEvent` helpers implemented
- [ ] All T7 tests pass

## Files Likely Affected
- `src/hyperadmin/core/realtime.py`

## Dependencies
Depends on: #308

## Notes for Implementer
JSON serialization via `json.dumps`/`json.loads`. Keep `pk` as `str` in serialized form for JSON compatibility.
