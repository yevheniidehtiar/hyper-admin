---
type: story
id: 9lNSUSAbDxns
title: "test(concurrency): update_view OCC handling — hidden __version field + 409 response"
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
  issue_number: 318
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f3a214292836d0e6095d6a7d7b582f5bccecc11e17eae43cfb411535d50f5531
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:00:11Z
updated_at: 2026-03-29T07:00:11Z
---

## Context
The view layer must inject the version token into the edit form and handle conflicts when the form is submitted with a stale version.

## Acceptance Criteria
- [ ] Test: `update_form_view` injects `__version` hidden input with current value when OCC is enabled for the model
- [ ] Test: `update_form_view` does NOT inject `__version` when OCC disabled (no version field)
- [ ] Test: `update_view` extracts `__version` from form data and passes to `adapter.update(expected_version=...)`
- [ ] Test: on `StaleRecordError`, `update_view` returns HTTP 409 with `conflict_dialog.html` HTML fragment
- [ ] Test: `__force=true` in form data causes `update_view` to call `adapter.update(expected_version=None)` (force overwrite)
- [ ] Tests in `tests/unit/test_views_occ.py`

## Files Likely Affected
- `tests/unit/test_views_occ.py` (new)

## Dependencies
Depends on: #317

## Notes for Implementer
Tests must FAIL before T18. Mock the adapter to raise `StaleRecordError` on demand.
