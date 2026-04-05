---
type: story
id: l1FGoO4OChqu
title: "test(e2e): fieldset collapse/expand toggle in create/update forms"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
estimate: null
epic_ref:
  id: HMxZRjunTlAA
github:
  issue_number: 190
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c75d2f0486959413f8107afb6ad1b93f55a589edbae7728022330095f51004af
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:34:43Z
updated_at: 2026-03-28T19:46:02Z
---

> **Part of:** #38
> **Depends on:** #66

## Acceptance Criteria
- [ ] `tests/e2e/test_fieldsets.py`
- [ ] `page.get_by_role('button', name=...)` to trigger collapse
- [ ] Assert fieldset content hidden/visible — no CSS class selectors
- [ ] `poe test:e2e` green

## Files
- `tests/e2e/test_fieldsets.py` (new)

