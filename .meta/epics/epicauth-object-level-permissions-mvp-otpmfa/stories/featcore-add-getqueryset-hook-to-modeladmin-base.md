---
type: story
id: krPQ6bnY4R18
title: "feat(core): add get_queryset hook to ModelAdmin base"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - core
  - size:S
  - planned
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 479
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ae3e9db59ce1665e198e5f79ce37c96fd0343cee464df66511982f5df340acfd
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-02T14:02:22Z
updated_at: 2026-04-02T14:02:22Z
---

## Summary

Add an optional `get_queryset(request)` method to the ModelAdmin base class so users can override it per-model to restrict visible records based on the current request/user.

## Files to Change

- `src/hyperadmin/core/options.py` — add `get_queryset` as optional callable on AdminOptions or ModelAdmin

## Design

```python
# On AdminOptions or ModelAdmin base
async def get_queryset(self, request: Request) -> dict[str, Any]:
    """Override to restrict records visible to the current user.
    
    Returns a dict of filters merged into every query.
    Default: no filtering (empty dict).
    """
    return {}
```

## Scenarios

**Scenario: default get_queryset returns no filters**
  Given a model with default ModelAdmin
  When  `get_queryset(request)` is called
  Then  result is `{}`

**Scenario: custom get_queryset filters by user**
  Given a ModelAdmin overriding `get_queryset` to return `{"owner_id": request.state.user.id}`
  When  user with id=5 visits the list view
  Then  adapter receives filters including `owner_id=5`

## Acceptance Criteria

- [ ] `get_queryset` method added to ModelAdmin / AdminOptions
- [ ] Default returns empty dict (backward compatible)
- [ ] Signature accepts `Request` parameter

## Blocked by

- #478 (adapter get_queryset hook)

## Parent

- Epic: #473
