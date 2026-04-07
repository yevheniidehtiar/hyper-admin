---
type: story
id: K3AnRMAHW2sv
title: "feat(adapters): add aggregation helpers to BaseAdapter"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - area:adapters
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 459
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:20ca319c60589236fa4a23bc37007d75768723bbb09898b3270eaed690f00c4c
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:44:20Z
updated_at: 2026-04-01T21:44:20Z
---

## Context

Dashboard widgets need aggregation capabilities (count, sum, avg) that don't exist in the current adapter API. This adds `count()` and `aggregate()` methods.

## Scenarios

**Scenario: count() returns total records matching filters**
  Given 10 Order records, 3 with `status="pending"`
  When  `count(filters={"status": "pending"})` is called
  Then  the result is 3

**Scenario: aggregate("amount", "sum") returns sum of field values**
  Given Order records with amounts `[100, 200, 300]`
  When  `aggregate("amount", "sum")` is called
  Then  the result is 600

**Scenario: count() with no filters returns total record count**
  Given 10 Order records
  When  `count()` is called with no filters
  Then  the result is 10

## Acceptance Criteria

- [ ] `count(filters) -> int` added to `BaseAdapter` (abstract with default)
- [ ] `aggregate(field, func, filters) -> Any` added to `BaseAdapter` (abstract with default)
- [ ] `SQLModelAdapter.count()` uses `func.count()` with optional filters
- [ ] `SQLModelAdapter.aggregate()` supports "sum", "avg", "min", "max"
- [ ] Both methods have default implementations raising `NotImplementedError`
- [ ] Unit tests cover all 3 scenarios + unsupported func

## Files Likely Affected
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `tests/unit/test_dashboard_adapters.py` (new) or extend existing adapter tests

## Dependencies
Depends on: #455 (SDD approved — design must be stable)

## Notes for Implementer
- `count()` is simpler than existing `list()` — just `select(func.count()).select_from(model)`
- `aggregate()` maps func name to SQLAlchemy functions: `func.sum`, `func.avg`, etc.
- Keep backward compatible: default implementations in `BaseAdapter` raise `NotImplementedError`
- These methods don't need `request` — they're used by the dashboard service, not views
