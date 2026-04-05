---
type: story
id: Z0akFhUQotCW
title: "feat(adapters): implement configurable selectinload in SQLModelAdapter and SQLAlchemyAdapter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:adapters
  - size:M
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 217
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:17bd46476e20322436183afd19373cb3bd53666cd59fd2e29ba60f765943f5a5
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:38:58Z
updated_at: 2026-03-29T18:26:32Z
---

## Context
Part of Epic #211 (A1: Configurable relationship loading strategy).

## Acceptance criteria
- [ ] `SQLModelAdapter.list()` only applies `selectinload()` for relations in `load_relations` list
- [ ] `SQLModelAdapter.get()` same behavior
- [ ] `SQLAlchemyAdapter.list()` and `.get()` same behavior
- [ ] When `load_relations=None`, all relations loaded (backward compat)
- [ ] When `load_relations=[]`, no `selectinload()` applied
- [ ] All tests from A1.1 pass

## Files
- `src/hyperadmin/adapters/sqlmodel.py` (lines 34-36, 54-57)
- `src/hyperadmin/adapters/sqlalchemy.py`

## Dependencies
- Blocked by: #216 (A1.2 core contract)
- Blocking: A1.4
