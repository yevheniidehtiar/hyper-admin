---
type: story
id: st-v058-byoa-22
title: "refactor(adapters): pk-agnostic get/get_related/update/delete/get_choices/save_inline_rows"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:adapters
  - layer:logic
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Use `self.pk` in both adapters:
- parse keys, and return `None` or `[]` when parsing fails;
- strip primary-key attributes in `update()`;
- set canonical choice values from the target model's key;
- coerce cascade filter values;
- check `_pk is not None`;
- raise `NotImplementedError` for composite keys.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.3

## Files to Change

- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `tests/unit/test_sqlmodel_adapter.py`
- `tests/unit/test_sqlalchemy_adapter.py`

## Scenarios

```
Scenario: get by UUID string
  Given a UUID-keyed row
  When  adapter.get(str(uuid)) runs
  Then  the row is returned

Scenario: garbage key returns None
  Given a UUID-keyed model on SQLite
  When  adapter.get('garbage') runs
  Then  None is returned

Scenario: update does not change the pk
  Given update data containing the pk attr
  When  adapter.update runs
  Then  the pk is unchanged

Scenario: UUID choice values
  Given a UUID-keyed target model
  When  get_choices runs
  Then  option values are canonical UUID strings

Scenario: UUID cascade filter
  Given a cascading filter country_id=<uuid str>
  When  get_choices runs
  Then  rows are filtered without bind errors

Scenario: pk 0 inline delete
  Given an inline row with _pk=0 and _delete
  When  save_inline_rows runs
  Then  the delete is executed
```

## Acceptance Criteria

- [ ] get by UUID string
- [ ] garbage key returns None
- [ ] update does not change the pk
- [ ] UUID choice values
- [ ] UUID cascade filter
- [ ] pk 0 inline delete
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featadapters-introspection-of-primary-keys-datetime-kinds-an` (st-v058-byoa-15)
- `featcore-session-factory-seam-on-baseadapter-adapters-and-au` (st-v058-byoa-21)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
