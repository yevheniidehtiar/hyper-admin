---
type: story
id: st-v055-bulk-01
title: "feat(core): extend ActionDef and @action with bulk/form parameters"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - backend
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Add `bulk: bool` and `form: type[BaseModel] | None` to `ActionDef` and the
`@action` decorator. Validate at decoration time that `form is not None`
implies `bulk is True`, and that the handler signature accepts a `params=None`
keyword when `bulk=True`.

**Spec:** [`docs/specs/bulk-actions.md`](../../../../docs/specs/bulk-actions.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/actions.py` — extend dataclass and decorator
- **Modified:** `tests/unit/test_actions.py` (new file if missing) — decoration-time validation tests

## Scenarios

```
Scenario: @action(form=X) without bulk=True raises TypeError
  When  @action(label="x", form=ReassignParams) is applied to a handler
  Then  a TypeError is raised with message "form= requires bulk=True"

Scenario: @action(bulk=True) accepts a handler with params kwarg
  Given async def archive(self, request, item_id, *, params=None): ...
  When  @action(label="Archive", bulk=True) is applied
  Then  the decorator returns the function unchanged
  And   handler._action_def.bulk is True

Scenario: legacy single-record @action(label="X") still works
  Given async def deactivate(self, request, item_id): ...
  When  @action(label="Deactivate") is applied
  Then  handler._action_def.bulk is False
  And   handler._action_def.form is None
```

## Acceptance Criteria

- [ ] `ActionDef` gains `bulk: bool = False`, `form: type[BaseModel] | None = None`
- [ ] `@action` accepts `bulk=`, `form=` keyword args
- [ ] Decoration-time `TypeError` when `form` set without `bulk`
- [ ] Decoration-time `TypeError` when `bulk=True` handler signature lacks `params` kwarg
- [ ] Legacy decoration paths unchanged
- [ ] Unit tests cover all three scenarios above
- [ ] `poe lint` passes

## Blocked by

- `reviewspec-approve-sdd-bulk-actions`

## Parent

- Epic: `epic-v055-bulk-actions`
