---
type: story
id: lyTZjicpWvJq
title: "feat(realtime): Emit RealtimeEvents from SQLModelAdapter + SQLAlchemyAdapter"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 311
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:84eb1ebc1b0b5fdb79614a39480289f23153a88d8d045373875c1890097a7d21
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:59:02Z
updated_at: 2026-03-29T06:59:03Z
---

## Context
Adapters are the source of truth for data mutations. They must notify the real-time layer after each successful CRUD operation.

## Acceptance Criteria
- [ ] `SQLModelAdapter` and `SQLAlchemyAdapter` accept optional `pubsub: PubSubBackend | None = None` in constructor
- [ ] After each `create/update/delete`, if `pubsub` is set: publish `RealtimeEvent` to channel `f'admin:{model_name}'`
- [ ] `Admin` class injects `pubsub_backend` into adapter instances on startup
- [ ] All T9 tests pass
- [ ] No behavior change when `pubsub=None`

## Files Likely Affected
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `src/hyperadmin/core/app.py`

## Dependencies
Depends on: #310

## Notes for Implementer
Emit AFTER successful commit, not before. Use `asyncio.create_task()` for fire-and-forget publish to avoid blocking the response.
