---
type: story
id: Vc4o46lg9kBJ
title: "test(concurrency): version_field detection + StaleRecordError unit tests"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - area:concurrency
estimate: null
epic_ref: null
github:
  issue_number: 314
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:beb24fbf0b6648bde32e864483a77281da70436dd48a600468fdb9efdd7a9449
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T06:59:35Z
updated_at: 2026-03-29T06:59:35Z
---

## Context
Foundation of the OCC feature. The version field detection logic determines whether a model has a field that can be used as a concurrency token, enabling conflict detection on concurrent edits.

## Acceptance Criteria
- [ ] Test: `detect_version_field(model_class, admin_options)` returns explicit `version_field` if set on `ModelAdmin`
- [ ] Test: returns first match from convention list `[updated_at, modified_at, last_modified, version]` when no explicit setting
- [ ] Test: returns `None` when no matching field found (OCC disabled)
- [ ] Test: `StaleRecordError` has `current_version` and `expected_version` attributes
- [ ] Test: `StaleRecordError` is a subclass of `Exception`
- [ ] Tests in `tests/unit/test_concurrency.py`

## Files Likely Affected
- `tests/unit/test_concurrency.py` (new)

## Dependencies
None — first task in Track B (independent of WebSocket track).

## Notes for Implementer
Tests must FAIL before T14. This track is fully independent of Track A and can be worked in parallel.
