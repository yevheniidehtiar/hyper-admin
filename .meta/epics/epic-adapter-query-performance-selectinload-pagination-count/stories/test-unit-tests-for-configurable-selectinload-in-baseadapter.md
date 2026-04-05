---
type: story
id: A2T5Egnw6EPg
title: "test: unit tests for configurable selectinload in BaseAdapter and SQLModelAdapter"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:adapters
  - size:M
  - performance
estimate: null
epic_ref:
  id: bz_SWmq9yUG6
github:
  issue_number: 215
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:09d7a9057cb4ea8994887b71f56115bbd6d40495577eb44ae7180d8df5c6a23c
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:38:50Z
updated_at: 2026-03-29T18:26:35Z
---

## Context
Part of Epic #211 (A1: Configurable relationship loading strategy).
Currently `selectinload()` is applied to ALL relationships on every `list()` and `get()` call, firing 5+ extra SELECTs per request on models with many relations.

## Acceptance criteria
- [ ] Test that `list()` accepts `load_relations: list[str] | None` parameter
- [ ] When `load_relations=None` (default), loads all relations (backward compat)
- [ ] When `load_relations=[]` (empty list), loads no relations
- [ ] When `load_relations=["customer"]`, loads only that relation
- [ ] Tests cover both SQLModelAdapter and SQLAlchemyAdapter
- [ ] Tests verify no N+1 queries when relations are loaded

## Files
- `tests/unit/test_adapter_selectinload.py` (new)

## Dependencies
- Blocked by: none
- Blocking: #A1.2
