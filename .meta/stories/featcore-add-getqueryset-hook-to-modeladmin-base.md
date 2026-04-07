---
type: story
id: e2JHGXLK6wgu
title: "feat(core): add get_queryset hook to ModelAdmin base"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 427
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:2142afc144b88737e240b641a2c4fe24778d76f666b5e2a55afce525594db7cc
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:37:27Z
updated_at: 2026-04-01T21:37:27Z
---

## Context

With the adapter-level `get_queryset()` hook in place (#426), users need a way to define query filtering at the ModelAdmin level (the user-facing configuration surface). This adds an overridable `get_queryset()` method to `ModelAdmin` that the adapter delegates to.

## Scenarios

**Scenario: ModelAdmin.get_queryset returns unmodified query by default**
  Given a `ModelAdmin` subclass with no `get_queryset` override
  When  `get_queryset(request, query, "view")` is called
  Then  the original query is returned unchanged

**Scenario: ModelAdmin subclass can override get_queryset for row filtering**
  Given a `ModelAdmin` subclass filtering `query.where(Model.owner_id == request.state.user.id)`
  When  `get_queryset()` is called
  Then  the filtered query is returned

## Acceptance Criteria

- [ ] `get_queryset(self, request, query, action)` method added to `ModelAdmin` in `core/model.py`
- [ ] Default implementation returns `query` unchanged
- [ ] Unit tests cover both scenarios
- [ ] Existing tests pass

## Files Likely Affected
- `src/hyperadmin/core/model.py`
- `tests/unit/test_model.py`

## Dependencies
Depends on: #426 (get_queryset hook in BaseAdapter)

## Notes for Implementer
- `ModelAdmin` is in `src/hyperadmin/core/model.py`
- Signature: `def get_queryset(self, request: Any, query: Any, action: str) -> Any`
- This is NOT async — it only modifies a query object, no DB calls
- The adapter will call `admin_instance.get_queryset()` if the admin_instance is available
