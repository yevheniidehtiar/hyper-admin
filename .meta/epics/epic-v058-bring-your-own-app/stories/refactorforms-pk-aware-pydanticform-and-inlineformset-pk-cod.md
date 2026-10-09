---
type: story
id: st-v058-byoa-31
title: "refactor(forms): pk-aware PydanticForm and InlineFormset pk codec"
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

`PydanticForm` gains `pk_attr`, `pk_editable` and `timezone`, which default to today's behaviour. `InlineFormset` gets `pk` from the inline model's adapter, replaces `int(pk_val)` with `pk.parse`, and types `parent_pk` as `Any`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.6

## Files to Change

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_forms.py`
- `tests/unit/test_inline_formset.py`

## Scenarios

```
Scenario: natural pk on create
  Given a natural str pk model
  When  the create form is built with pk_editable=True
  Then  'code' is a required field

Scenario: defaults are back-compatible
  Given PydanticForm defaults
  When  the form is built
  Then  'id' is skipped

Scenario: inline UUID pk
  Given an inline model with a UUID pk
  When  the submitted '-pk' is a UUID string
  Then  the row updates that UUID

Scenario: inline invalid pk
  Given an inline '-pk' value that is not a valid UUID
  When  the formset validates
  Then  the row is rejected with an error
```

## Acceptance Criteria

- [ ] natural pk on create
- [ ] defaults are back-compatible
- [ ] inline UUID pk
- [ ] inline invalid pk
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- `InlineFormset` never trusts a submitted pk on its own. Ownership is enforced by the adapter (`-10`), and this story keeps that check while switching to `pk.parse`.

## Blocked by

- `refactorviews-dynamicmodelview-item-handlers-use-self-pk-and` (st-v058-byoa-29)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
