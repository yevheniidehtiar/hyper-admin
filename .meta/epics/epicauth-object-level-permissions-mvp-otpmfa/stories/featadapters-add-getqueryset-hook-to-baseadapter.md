---
type: story
id: WBkpbZr3AYYS
title: "feat(adapters): add get_queryset hook to BaseAdapter"
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
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 426
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7393596c972705f8e6193d1aa72562bd383104037981008dabd2466596c26c10
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:37:15Z
updated_at: 2026-04-01T21:37:15Z
---

## Context

Currently, `BaseAdapter.list()` has no way to inject per-request query filtering. All queries return the full dataset. For row-level security and multi-tenancy, we need a `get_queryset()` hook that can modify the base query before filtering/search/pagination is applied.

This is the critical architectural change that enables both object-level permissions (Epic #419) and multi-tenancy (Epic #421).

## Scenarios

**Scenario: BaseAdapter.get_queryset returns unfiltered query by default**
  Given a `SQLModelAdapter` with no `get_queryset` override
  When  `list()` is called
  Then  all records are returned (no additional filtering)

**Scenario: overridden get_queryset filters by user ownership**
  Given a `SQLModelAdapter` with `get_queryset` filtering where `owner_id == request.state.user.id`
  When  `list()` is called with `request.state.user.id = 5`
  Then  only records with `owner_id = 5` are returned

**Scenario: get_queryset receives request and action parameters**
  Given a custom `get_queryset` implementation logging its parameters
  When  `list()` is called with `action="view"`
  Then  the hook receives the request object and `action="view"`

## Acceptance Criteria

- [ ] `get_queryset(request, query, action)` method added to `BaseAdapter` with default pass-through
- [ ] `SQLModelAdapter.list()` calls `get_queryset()` before applying filters/search/ordering
- [ ] `list()` signature gains optional `request` parameter (backward compatible: defaults to None)
- [ ] `get()` also calls `get_queryset()` for single-object scoping
- [ ] All existing tests pass (backward compatible)
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/core/adapters.py` — add `get_queryset()` to BaseAdapter
- `src/hyperadmin/adapters/sqlmodel.py` — implement hook in `list()` and `get()`
- `tests/unit/test_object_permissions.py` (new)
- `tests/unit/adapters/` (existing adapter tests)

## Dependencies
Depends on: #423 (SDD approved)

## Notes for Implementer
- `list()` signature change must be backward compatible: `request: Any | None = None`
- `get_queryset()` receives the base `select(self.model)` query and returns a modified `Select`
- Default implementation: `return query` (no filtering)
- This is the foundation for multi-tenancy (Epic #421) — design for extensibility
- The `request` parameter flows from the view layer; adapters themselves don't import HTTP types
- CONSTITUTION.md: `adapters/` must not import from `views/`
