---
type: story
id: CiS8TcNwf05S
title: "feat(concurrency): OCC in BaseAdapter + SQLModelAdapter + SQLAlchemyAdapter"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:concurrency
estimate: null
epic_ref: null
github:
  issue_number: 317
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d3e3246522c4f1d81125819673ef4ada6f4649c62a4c596d85e89aff25f85199
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:00:00Z
updated_at: 2026-03-29T07:00:00Z
---

## Context
Implements the concurrency check at the data layer — the only place where the check can be performed atomically.

## Acceptance Criteria
- [ ] `BaseAdapter.update(pk, data, *, expected_version=None)` signature updated
- [ ] `SQLModelAdapter.update()`: if `expected_version` set and version_field detected, fetch current version; if mismatch raise `StaleRecordError`
- [ ] `SQLAlchemyAdapter.update()`: same logic
- [ ] Integer `version` fields auto-incremented on save
- [ ] `datetime` version fields auto-updated to `utcnow()` on save
- [ ] All T15 tests pass

## Files Likely Affected
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`

## Dependencies
Depends on: #316

## Notes for Implementer
Fetch current version BEFORE update in same transaction. The check must be atomic: use `SELECT ... FOR UPDATE` or check-then-update within a transaction to prevent TOCTOU. Raise `StaleRecordError` before executing the UPDATE.
