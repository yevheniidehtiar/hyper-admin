---
type: story
id: st-v058-byoa-30
title: "refactor(views): bulk ids, single actions and popup payload are pk-type-agnostic"
status: todo
priority: high
assignee: null
labels:
  - size:S
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

`_parse_ids` uses `pk.parse` and silently drops invalid values. Bulk types become `list[Any]`. The popup `id` uses `pk.to_json`, and action handlers receive the typed key.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.6

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/core/actions.py`
- `src/hyperadmin/core/bulk_results.py`
- `tests/unit/test_bulk_actions.py`
- `tests/unit/test_actions.py`
- `tests/unit/test_popup_create.py`

## Scenarios

```
Scenario: UUID bulk
  Given two UUID ids posted to the bulk endpoint
  When  the bulk action runs
  Then  two outcomes with status ok are returned

Scenario: unparseable id dropped
  Given an unparseable id in a bulk post
  When  the bulk action runs
  Then  it is dropped silently

Scenario: UUID popup id
  Given a popup create on a UUID model
  When  it succeeds
  Then  HX-Trigger id is a UUID string

Scenario: int popup id
  Given a popup create on an int model
  When  it succeeds
  Then  HX-Trigger id is a JSON number

Scenario: typed action id
  Given a single action on a UUID row
  When  it runs
  Then  the handler receives a uuid.UUID item_id
```

## Acceptance Criteria

- [ ] UUID bulk
- [ ] unparseable id dropped
- [ ] UUID popup id
- [ ] int popup id
- [ ] typed action id
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactorviews-dynamicmodelview-item-handlers-use-self-pk-and` (st-v058-byoa-29)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
