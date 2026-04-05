---
type: story
id: CyjNeSV2HHf9
title: "test(realtime): CRUD event emission from adapters"
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
  issue_number: 310
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d283ec555ebaf5d9e1ee62eb71f6ea7860272778e919572207c4bc0b2f356b4b
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:58:53Z
updated_at: 2026-03-29T06:58:53Z
---

## Context
Adapters must emit RealtimeEvents after successful CRUD operations so the notification system can broadcast to connected clients.

## Acceptance Criteria
- [ ] Test: after `adapter.create()`, if `pubsub` is set, a `RealtimeEvent(action=created)` is published to channel `admin:{model_name}`
- [ ] Test: after `adapter.update()`, event with `action=updated` published
- [ ] Test: after `adapter.delete()`, event with `action=deleted` published
- [ ] Test: correct `pk` in all events
- [ ] Test: NO emission when `pubsub=None` (backward compat — no regression)
- [ ] Tests cover both SQLModelAdapter and SQLAlchemyAdapter
- [ ] Tests in `tests/unit/test_adapter_events.py`

## Files Likely Affected
- `tests/unit/test_adapter_events.py` (new)

## Dependencies
Depends on: #309

## Notes for Implementer
Tests must FAIL before T10. Use pytest-mock to mock the PubSubBackend.
