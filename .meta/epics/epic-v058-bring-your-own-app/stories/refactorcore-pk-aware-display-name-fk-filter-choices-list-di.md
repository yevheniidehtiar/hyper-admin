---
type: story
id: st-v058-byoa-23
title: "refactor(core): pk-aware display name, FK filter choices, list_display fallback and inline display fields"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:core
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Replace hard-coded `id` in `core/display.py`, `core/discovery.py:89`, `core/introspection.py:153,162` and `core/inlines.py`, using the primary-key metadata that already exists.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.4

## Files to Change

- `src/hyperadmin/core/display.py`
- `src/hyperadmin/core/discovery.py`
- `src/hyperadmin/core/introspection.py`
- `src/hyperadmin/core/inlines.py`
- `tests/unit/test_display.py`
- `tests/unit/test_introspection.py`

## Scenarios

```
Scenario: display name falls back to the pk
  Given a model with pk 'code' and no name attribute
  When  get_display_name(pk_attr='code') runs
  Then  'Country (NL)' is returned

Scenario: list_display fallback
  Given a model with UUID pk 'uuid'
  When  infer_list_display falls back
  Then  ['uuid', '__str__'] is returned

Scenario: inline display excludes pk
  Given an inline model with pk 'uuid'
  When  get_display_fields(pk_attr='uuid') runs
  Then  'uuid' is excluded

Scenario: FK filter choices
  Given an FK to a UUID model
  When  filter metadata is built
  Then  choice values are UUID strings
```

## Acceptance Criteria

- [ ] display name falls back to the pk
- [ ] list_display fallback
- [ ] inline display excludes pk
- [ ] FK filter choices
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-primarykeyinfo-codec-invalidprimarykey-and-baseadap` (st-v058-byoa-13)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
