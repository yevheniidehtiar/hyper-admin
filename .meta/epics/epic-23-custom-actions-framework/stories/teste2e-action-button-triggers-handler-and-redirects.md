---
type: story
id: lxfqXIchVvaD
title: "test(e2e): action button triggers handler and redirects"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
estimate: null
epic_ref:
  id: kR3DYwg4B6e2
github:
  issue_number: 187
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:76a323d93d075e5b0c03f6eb3cccbc5048f17e39a845cf41bf6b10f3f2d34042
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:34:16Z
updated_at: 2026-03-28T19:44:54Z
---

> **Part of:** #41
> **Depends on:** #70

## Acceptance Criteria
- [ ] `tests/e2e/test_actions.py`
- [ ] `page.get_by_test_id('action-{name}-btn')`
- [ ] Assert success flash message or redirect to list
- [ ] `poe test:e2e` green

## Files
- `tests/e2e/test_actions.py` (new)

