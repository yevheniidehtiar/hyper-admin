---
type: story
id: WSzsCVC1pZgM
title: "feat(adapters): add get_queryset hook to BaseAdapter + SQLModelAdapter"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:M
  - planned
  - adapters
estimate: null
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 478
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9c8a39ef31f121aead6527fce3e1d11058b1cd4fd39fef359beb124362a59a02
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T14:02:08Z
updated_at: 2026-04-02T14:02:08Z
---

## Summary

Add a `get_queryset()` hook to `BaseAdapter` and implement it in `SQLModelAdapter` / `SQLAlchemyAdapter`. This hook allows injecting per-request query filters (e.g., row-level security, tenant scoping) before any list/get operation.

## Files to Change

- `src/hyperadmin/core/adapters.py` — add abstract `get_queryset()` method to `BaseAdapter`
- `src/hyperadmin/adapters/sqlmodel.py` — implement in `SQLModelAdapter.list()` and `get()`
- `src/hyperadmin/adapters/sqlalchemy.py` — implement in `SQLAlchemyAdapter.list()` and `get()`

## Design

```python
# In BaseAdapter
def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
    """Return additional filters to apply to all queries.
    
    Override in subclass or set via set_queryset_filter() to restrict
    records visible to the current user/tenant.
    """
    return {}

def set_queryset_filter(self, filter_fn: Callable[[Request], dict[str, Any]]) -> None:
    """Set a callable that returns per-request filters."""
    self._queryset_filter = filter_fn
```

In `SQLModelAdapter.list()`, merge `get_queryset()` filters into the query before other filters.

## Scenarios

**Scenario: get_queryset filters are applied to list results**
  Given adapter has `get_queryset()` returning `{"owner_id": 1}`
  When  `adapter.list()` is called
  Then  SQL query includes `WHERE owner_id = 1`
  And   only matching records are returned

**Scenario: get_queryset filters are applied to get() results**
  Given adapter has `get_queryset()` returning `{"owner_id": 1}`
  When  `adapter.get(pk=5)` is called for a record with owner_id=2
  Then  result is `None` (record filtered out)

**Scenario: empty get_queryset returns all records (backward compatible)**
  Given adapter has default `get_queryset()` returning `{}`
  When  `adapter.list()` is called
  Then  all records are returned (no extra filtering)

**Scenario: get_queryset count reflects filtered results**
  Given 100 records total, 30 matching `{"owner_id": 1}`
  When  `adapter.list()` is called with queryset filter `{"owner_id": 1}`
  Then  total count is 30

## Acceptance Criteria

- [ ] `get_queryset()` method added to `BaseAdapter`
- [ ] `SQLModelAdapter.list()` merges queryset filters
- [ ] `SQLModelAdapter.get()` applies queryset filters
- [ ] `SQLAlchemyAdapter` updated similarly
- [ ] Backward compatible — default returns empty dict
- [ ] Count query respects queryset filters

## Blocked by

- #475 (spec approval)

## Parent

- Epic: #473
