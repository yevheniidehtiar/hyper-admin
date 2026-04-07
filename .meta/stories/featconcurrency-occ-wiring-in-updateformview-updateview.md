---
type: story
id: szvf5C4et3FM
title: "feat(concurrency): OCC wiring in update_form_view + update_view"
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
  issue_number: 319
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cbbb348fed832e174595181733c2f369182132ce35a2184381a2a32f7221b482
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:00:21Z
updated_at: 2026-03-29T07:00:21Z
---

## Context
Wires the OCC logic into the HTTP layer — injecting version tokens into forms and handling conflicts gracefully.

## Acceptance Criteria
- [ ] `update_form_view` in `views/dynamic.py`: if `detect_version_field()` returns a field, fetch current value and add `__version` to template context
- [ ] `update_view`: extract `__version` from form data; pass as `expected_version` to `adapter.update()`
- [ ] On `StaleRecordError`: return HTTP 409 + render `conflict_dialog.html` fragment (HTMX-swappable)
- [ ] On `__force=true` in form: call `adapter.update(expected_version=None)`
- [ ] All T17 tests pass
- [ ] Backward compatible: models without version field unaffected

## Files Likely Affected
- `src/hyperadmin/views/dynamic.py`

## Dependencies
Depends on: #318

## Notes for Implementer
Return 409 with HTMX-compatible response (`HX-Retarget` header to swap conflict dialog into `#model-form-body`). Follow existing HTMX response patterns in `views/dynamic.py`.
