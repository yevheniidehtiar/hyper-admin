---
type: story
id: B4xiMaz6vCvV
title: "feat(auth): create ObjectPermission protocol"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:S
  - planned
  - auth
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 476
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:abb4f0051242d7fa4dc11acbbcb068d0c29dad44f774039f4574f002a41e636b
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-02T13:53:20Z
updated_at: 2026-04-02T13:53:21Z
---

## Summary

Define the `ObjectPermission` protocol in `core/auth.py` that enables per-object permission checks. This protocol complements the existing model-level `PermissionChecker`.

## Files to Change

- `src/hyperadmin/core/auth.py` — add `ObjectPermissionChecker` protocol

## Design

```python
@runtime_checkable
class ObjectPermissionChecker(Protocol):
    async def has_object_permission(
        self, user: Any, obj: Any, action: str
    ) -> bool: ...
```

- `action` uses same codenames as model-level: "view", "add", "change", "delete"
- Superuser bypass is the responsibility of the implementation, not the protocol
- Default implementation returns `True` (permissive by default)

## Scenarios

**Scenario: protocol is runtime-checkable**
  Given a class implementing `has_object_permission(user, obj, action) -> bool`
  When  `isinstance(instance, ObjectPermissionChecker)` is evaluated
  Then  result is `True`

**Scenario: default implementation allows all access**
  Given `DefaultObjectPermissionChecker` is used
  When  `has_object_permission(user, order, "view")` is called
  Then  result is `True`

## Acceptance Criteria

- [ ] Protocol defined and runtime-checkable
- [ ] Default permissive implementation provided
- [ ] Exported in `core/auth.py` and `core/__init__.py`

## Blocked by

- #475 (spec approval)

## Parent

- Epic: #473
