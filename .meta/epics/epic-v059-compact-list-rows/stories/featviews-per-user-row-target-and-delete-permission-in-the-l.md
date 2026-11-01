---
type: story
id: st-v059-list-01
title: "feat(views): per-user row target and delete permission in the list context"
status: backlog
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - backend
estimate: null
epic_ref:
  id: ep-v059-list-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Seam story. `list_view` adds `row_target` (`"update"`, `"detail"` or `None`) and `user_can_delete` to the template context, from `options.can_*` plus the user's `change_` / `view_` / `delete_<model>` permissions. At most two permission checks per render; object permissions stay server-side on open.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic/list_view.py`
- **Modified:** `tests/unit/test_list_view.py`

## Scenarios

```
Scenario: an editor's rows target the edit page
  Given alice holds change_order
  When  alice requests the order list
  Then  the context has row_target="update"

Scenario: a read-only user's rows target the detail page
  Given bob holds view_order but not change_order
  When  bob requests the order list
  Then  row_target is "detail" and user_can_delete is false

Scenario: can_edit=False forces detail even for editors
  Given AdminOptions(can_edit=False) and alice holds change_order
  When  alice requests the list
  Then  row_target is "detail"

Scenario: no auth means full access
  Given HyperAdmin without a permission checker
  When  the list renders
  Then  row_target is "update" and user_can_delete follows can_delete
```

## Acceptance Criteria

- [ ] No per-row permission calls added
- [ ] Existing `can_*` context keys kept
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass

## Notes for Implementer

Hotspot owner for `list_view.py` in this milestone.

## Blocked by

- `reviewspec-approve-navigation-and-list-ux-sdd` (st-v059-nav-00)

## Parent

- Epic: `epic-v059-compact-list-rows`
