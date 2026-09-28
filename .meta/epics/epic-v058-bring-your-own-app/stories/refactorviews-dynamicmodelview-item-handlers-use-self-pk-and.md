---
type: story
id: st-v058-byoa-29
title: "refactor(views): DynamicModelView item handlers use self.pk and _resolve_pk"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Change every item handler to take `item_id: Any` and call `_resolve_pk`, which turns `InvalidPrimaryKey` into a 404. List rows carry `_pk`, and still carry `id` for int-id models. `pk_attr` goes into the template context. On update, natural keys are handled with a `setdefault` before validation and a `pop` after it.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.6

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_dynamic_view_htmx.py`
- `tests/unit/test_dynamic_view_pk_types.py`

## Scenarios

```
Scenario: UUID detail
  Given a UUID row
  When  detail_view runs
  Then  the status is 200

Scenario: invalid pk update 404
  Given item_id='zzz' for a UUID model
  When  update_view runs
  Then  HTTP 404 is raised

Scenario: pk not overwritten
  Given a UUID model
  When  update_view saves
  Then  the pk is not replaced by a fresh uuid4

Scenario: natural pk update validates
  Given a natural str pk model
  When  update_view runs without a 'code' input
  Then  validation passes

Scenario: UUID create redirect
  Given a UUID model
  When  create succeeds
  Then  the redirect goes to the new row's detail URL

Scenario: rows keep id
  Given an int-id model
  When  list rows are built
  Then  each row has '_pk' and 'id'
```

## Acceptance Criteria

- [ ] UUID detail
- [ ] invalid pk update 404
- [ ] pk not overwritten
- [ ] natural pk update validates
- [ ] UUID create redirect
- [ ] rows keep id
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `fixviews-enforce-model-and-object-permissions-on-inline-edit` (st-v058-byoa-10)
- `refactoradapters-pk-agnostic-get-get-related-update-delete-g` (st-v058-byoa-22)
- `refactorcore-pk-aware-display-name-fk-filter-choices-list-di` (st-v058-byoa-23)
- `featrouting-per-model-pk-convertor-hyperadmin-pk-convertor-l` (st-v058-byoa-28)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
