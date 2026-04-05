---
type: story
id: hI7hcr37-pIJ
title: "test(concurrency): BaseAdapter.update() with expected_version parameter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - area:concurrency
estimate: null
epic_ref: null
github:
  issue_number: 316
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:33a9c7cf10dff90e7da908d6f1f3fdc633dfc54efe1365174912d29bc6b40473
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:59:50Z
updated_at: 2026-03-29T06:59:50Z
---

## Context
The adapter layer must enforce the version check atomically — checking and updating in the same transaction to prevent TOCTOU races.

## Acceptance Criteria
- [ ] Test: `adapter.update(pk, data, expected_version=X)` raises `StaleRecordError` when DB version value differs from `X`
- [ ] Test: no error when `expected_version=None` (backward compat)
- [ ] Test: no error when version field not detected on model
- [ ] Test: successful update when `expected_version` matches DB value
- [ ] Tests use `SQLModelAdapter` with in-memory SQLite (aiosqlite)
- [ ] Tests in `tests/unit/test_adapter_occ.py`

## Files Likely Affected
- `tests/unit/test_adapter_occ.py` (new)

## Dependencies
Depends on: #315

## Notes for Implementer
Tests must FAIL before T16.
