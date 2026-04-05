---
type: story
id: hwYZkuLULJud
title: "test(e2e): FK relation select renders, submits, and redirects"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 183
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a68ef26fdefc6f163aed9669191d3d7e91c1aafef7da0cd10bcd3b25c32e24ff
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:33:41Z
updated_at: 2026-03-26T23:49:55Z
---

> **Part of:** #159
> **Depends on:** #169, #170

## Acceptance Criteria
- [ ] `tests/e2e/test_relation_widgets.py`
- [ ] `page.get_by_role('combobox')` — no CSS class selectors
- [ ] Preload mode: options present on page load
- [ ] Lazy mode: type query → assert HTMX partial updates options
- [ ] Submit form → assert redirect to list view
- [ ] `poe test:e2e` green

## Files
- `tests/e2e/test_relation_widgets.py` (new)

