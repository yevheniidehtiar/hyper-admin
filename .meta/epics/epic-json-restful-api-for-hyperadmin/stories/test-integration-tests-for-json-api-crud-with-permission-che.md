---
type: story
id: sL38TExGtK1z
title: "test: integration tests for JSON API CRUD with permission checks"
status: todo
priority: medium
assignee: null
labels:
  - area:tests
  - size:M
estimate: null
epic_ref:
  id: 0Ds0szEo93g1
github:
  issue_number: 201
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0bae74d39101701377b91e29f1adc47bad7e76e445e1951ceed87594a1c5357d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:42:00Z
updated_at: 2026-03-30T20:51:51Z
---

> **Part of:** #76
> **Depends on:** #199, #200

## Acceptance Criteria
- [ ] `tests/unit/test_json_api_crud.py` using `httpx.AsyncClient`
- [ ] All 5 CRUD endpoints covered for at least one model
- [ ] Unauthenticated → 401; wrong permission → 403
- [ ] Correct pagination meta in list response
- [ ] `poe test:unit` green

## Files
- `tests/unit/test_json_api_crud.py` (new)

