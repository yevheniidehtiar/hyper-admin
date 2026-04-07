---
type: story
id: GRr9-cj3oNeS
title: "test(e2e): OCC conflict detection — two sessions editing same record"
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
  issue_number: 321
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8e8e149c8126f6e3812559596052f0af7eba395d79ff2a33160a524f0590fb0d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:00:40Z
updated_at: 2026-03-29T07:00:40Z
---

## Context
End-to-end verification of the complete OCC pipeline: two admins edit the same record simultaneously; the second save is rejected with a conflict dialog; both resolution paths (reload and overwrite) work.

## Acceptance Criteria
- [ ] Two Playwright sessions open the same record edit form
- [ ] Session B submits successfully (first save wins)
- [ ] Session A submits → conflict dialog appears (HTTP 409, dialog rendered)
- [ ] **Reload path**: click Reload → form refreshes with Session B's data
- [ ] **Overwrite path**: click Save Anyway → form saves successfully, overrides Session B's data
- [ ] Test on a model that has a version field (`updated_at` or similar)
- [ ] Tests in `tests/e2e/test_occ_conflict.py`

## Files Likely Affected
- `tests/e2e/test_occ_conflict.py` (new)

## Dependencies
Depends on: #320

## Notes for Implementer
Follow existing E2E test patterns. Use `page.fill()` and `page.click()` for form interaction. Both sessions must operate on the same DB/server instance.
