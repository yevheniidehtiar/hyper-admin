---
type: story
id: st-v058-byoa-28
title: "feat(routing): per-model pk convertor, hyperadmin_pk convertor, literal routes first, composite list-only"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:routing
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Register the `hyperadmin_pk` converter, which percent-encodes. Choose `{item_id:<pk.path_convertor>}` per model. Register literal routes before item routes, and register composite-key models list-only with a warning. Int-key paths must stay byte-identical.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.5

## Files to Change

- `src/hyperadmin/routing.py`
- `tests/unit/test_routing_pk.py`

## Scenarios

```
Scenario: int paths unchanged
  Given an int-id model
  When  routes are generated
  Then  paths contain '{item_id:int}'

Scenario: malformed UUID 404
  Given a UUID model
  When  GET /m/not-a-uuid is requested
  Then  the status is 404

Scenario: literal route wins
  Given a str-pk model
  When  GET /m/create-popup?target=x is requested
  Then  the popup view handles it

Scenario: special characters round-trip
  Given a str pk 'a b?c'
  When  url_for(detail) runs
  Then  the path is percent-encoded and resolves back to 'a b?c'

Scenario: composite list-only
  Given a composite-pk model
  When  routes are generated
  Then  only list and choices routes exist
  And   a warning is logged
```

## Acceptance Criteria

- [ ] int paths unchanged
- [ ] malformed UUID 404
- [ ] literal route wins
- [ ] special characters round-trip
- [ ] composite list-only
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featadapters-introspection-of-primary-keys-datetime-kinds-an` (st-v058-byoa-15)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
