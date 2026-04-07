---
type: story
id: eHm5sgt4MF3K
title: "feat(concurrency): core/concurrency.py — version detection + StaleRecordError"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:S
  - area:concurrency
estimate: null
epic_ref: null
github:
  issue_number: 315
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f4e9875015476ae29742070d9f83179dd335d1a97261ef99619b645f14b269bf
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:59:42Z
updated_at: 2026-03-29T06:59:43Z
---

## Context
Core domain logic for optimistic concurrency control. Zero external dependencies — pure Python logic.

## Acceptance Criteria
- [ ] `src/hyperadmin/core/concurrency.py` created
- [ ] `detect_version_field(model_class, admin_options) -> str | None` implemented
- [ ] `StaleRecordError(current_version, expected_version)` exception class implemented
- [ ] `version_field: str | None = None` added to `ModelAdmin` / `AdminOptions`
- [ ] All T13 tests pass

## Files Likely Affected
- `src/hyperadmin/core/concurrency.py` (new)
- `src/hyperadmin/core/options.py`
- `src/hyperadmin/core/model.py`

## Dependencies
Depends on: #314

## Notes for Implementer
Convention detection: inspect `model_class.__fields__` (Pydantic) or `__table__.columns` (SQLAlchemy) for field names matching the convention list. Case-insensitive match.
