---
type: story
id: uA2sSfp4itit
title: "test: unit tests for configurable search_fields in adapter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:adapters
  - size:S
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
github:
  issue_number: 219
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:10ebcbf54928cbfc4e0f3429bc2f22bacdf35db59252c0a164ec902ad75fc063
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:39:18Z
updated_at: 2026-03-29T18:26:29Z
---

## Context
Part of Epic #211 (A2: Configurable search fields).
Currently search is hardcoded to `name` and `email` in SQLModelAdapter.

## Acceptance criteria
- [ ] Test that `list(search=...)` only searches fields specified in `search_fields`
- [ ] Test empty `search_fields=[]` disables search entirely
- [ ] Test backward compat: when `search_fields` not specified, uses current behavior
- [ ] Tests cover both SQLModelAdapter and SQLAlchemyAdapter

## Files
- `tests/unit/test_adapter_search.py` (new)

## Dependencies
- Blocked by: none
- Blocking: A2.2
