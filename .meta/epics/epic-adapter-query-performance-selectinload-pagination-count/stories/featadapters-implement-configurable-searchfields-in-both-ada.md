---
type: story
id: E8NRyOoojhfa
title: "feat(adapters): implement configurable search_fields in both adapters"
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
  id: fkINeqAy7AVG
github:
  issue_number: 221
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:464d6da0f0ac74f2e2adba78701c06dbfc521fcf9e8b5039bf3d202a972086b1
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:39:30Z
updated_at: 2026-03-29T18:26:27Z
---

## Context
Part of Epic #211 (A2: Configurable search fields).

## Acceptance criteria
- [ ] SQLModelAdapter replaces hardcoded `name`/`email` with dynamic `search_fields` list
- [ ] SQLAlchemyAdapter replaces "all string columns" search with `search_fields` list
- [ ] ILIKE applied only on specified columns
- [ ] When `search_fields` is empty/None, falls back to current behavior
- [ ] All tests from A2.1 pass

## Files
- `src/hyperadmin/adapters/sqlmodel.py` (lines 65-73)
- `src/hyperadmin/adapters/sqlalchemy.py` (lines 39-46)

## Dependencies
- Blocked by: #220 (A2.2 core contract)
- Blocking: A2.4
