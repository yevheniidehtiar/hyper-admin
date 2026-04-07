---
type: story
id: jERrprk0OO7H
title: "feat(core): add load_relations parameter to BaseAdapter.list() and .get()"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - size:M
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
github:
  issue_number: 216
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ce01242c72ef7984fde3b69af53844d91d7dd271cba0bd1b30e3706e9f5fb7ad
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:38:55Z
updated_at: 2026-03-29T18:26:33Z
---

## Context
Part of Epic #211 (A1: Configurable relationship loading strategy).

## Acceptance criteria
- [ ] `BaseAdapter.list()` signature includes `load_relations: list[str] | None = None`
- [ ] `BaseAdapter.get()` signature includes `load_relations: list[str] | None = None`
- [ ] `AdminOptions` gains `list_select_related: list[str] = []` and `detail_select_related: list[str] = []`
- [ ] Empty list means "load nothing"; `None` means "load all" (backward compat)
- [ ] All tests from A1.1 pass

## Files
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/options.py`

## Dependencies
- Blocked by: #215 (A1.1 tests)
- Blocking: A1.3
