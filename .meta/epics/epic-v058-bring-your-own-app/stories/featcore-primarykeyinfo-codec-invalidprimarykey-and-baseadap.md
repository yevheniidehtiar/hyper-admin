---
type: story
id: st-v058-byoa-13
title: "feat(core): PrimaryKeyInfo codec, InvalidPrimaryKey and BaseAdapter.pk/datetime_kind"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:core
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add a pure `core/primary_key.py` with `PrimaryKeyInfo` (methods `parse`, `to_str`, `to_json`, `value_of` and `path_convertor`), `InvalidPrimaryKey` and `DEFAULT_PK`. Also add the non-abstract `BaseAdapter.pk` attribute and the `BaseAdapter.datetime_kind()` method, so third-party adapters keep working unchanged.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.1

## Files to Change

- `src/hyperadmin/core/primary_key.py`
- `src/hyperadmin/core/adapters.py`
- `src/hyperadmin/core/__init__.py`
- `tests/unit/test_primary_key.py`

## Scenarios

```
Scenario: invalid UUID raises InvalidPrimaryKey
  Given PrimaryKeyInfo(python_type=uuid.UUID)
  When  parse('not-a-uuid') is called
  Then  InvalidPrimaryKey is raised

Scenario: int keys stay numeric in JSON
  Given an int PrimaryKeyInfo
  When  to_json(7) is called
  Then  the int 7 is returned

Scenario: empty string key is rejected
  Given a str PrimaryKeyInfo
  When  parse('') is called
  Then  InvalidPrimaryKey is raised

Scenario: third-party adapter gets the default pk
  Given a BaseAdapter subclass that does not set pk
  When  pk is read
  Then  DEFAULT_PK with attr 'id' and type int is returned
```

## Acceptance Criteria

- [ ] invalid UUID raises InvalidPrimaryKey
- [ ] int keys stay numeric in JSON
- [ ] empty string key is rejected
- [ ] third-party adapter gets the default pk
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
