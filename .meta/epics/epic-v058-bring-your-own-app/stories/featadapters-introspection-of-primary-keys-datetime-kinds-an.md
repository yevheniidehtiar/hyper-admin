---
type: story
id: st-v058-byoa-15
title: "feat(adapters): introspection of primary keys, datetime kinds and column value coercion"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:adapters
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `adapters/introspection.py` with three functions:
- `introspect_primary_key(model)`, using the SQLAlchemy mapper. It resolves the attribute key, the Python type, `generated` and `composite`.
- `datetime_kind(model, field)`, covering `AwareDatetime`/`NaiveDatetime`, `hyperadmin_tz_aware`, `UTCDateTime` and `DateTime(timezone=)`.
- `coerce_column_value`, which delegates to `core.filtering.coerce_filter_value`.

Then set `pk` and implement `datetime_kind` in `SQLModelAdapter` and `SQLAlchemyAdapter`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.2

## Files to Change

- `src/hyperadmin/adapters/introspection.py`
- `src/hyperadmin/adapters/__init__.py`
- `src/hyperadmin/adapters/sqlmodel.py`
- `src/hyperadmin/adapters/sqlalchemy.py`
- `tests/unit/test_pk_introspection.py`
- `tests/unit/test_datetime_kind.py`

## Scenarios

```
Scenario: int autoincrement id
  Given a model with an int autoincrement id
  When  introspect_primary_key runs
  Then  pk is attr 'id', type int, generated True

Scenario: UUID with default_factory
  Given a model with id: UUID = Field(default_factory=uuid4, primary_key=True)
  When  introspect_primary_key runs
  Then  kind is 'uuid' and generated is True

Scenario: natural string key
  Given a model with code: str primary key and no default
  When  introspect_primary_key runs
  Then  kind is 'str' and generated is False

Scenario: remapped column
  Given a pk mapped via sa_column=Column('id') under attribute 'id_'
  When  introspect_primary_key runs
  Then  attr is 'id_'

Scenario: composite key
  Given a two-column primary key
  When  introspect_primary_key runs
  Then  composite is True

Scenario: naive DateTime column
  Given a column DateTime(timezone=False)
  When  datetime_kind runs
  Then  'naive' is returned

Scenario: UTCDateTime column
  Given sqlmodel UTCDateTime is importable (skip otherwise)
  When  datetime_kind runs
  Then  'aware' is returned

Scenario: annotation wins
  Given annotation NaiveDatetime on a DateTime(timezone=True) column
  When  datetime_kind runs
  Then  'naive' is returned

Scenario: UUID fk coercion
  Given a UUID fk column
  When  coerce_column_value runs with a UUID string
  Then  a uuid.UUID is returned
```

## Acceptance Criteria

- [ ] int autoincrement id
- [ ] UUID with default_factory
- [ ] natural string key
- [ ] remapped column
- [ ] composite key
- [ ] naive DateTime column
- [ ] UTCDateTime column
- [ ] annotation wins
- [ ] UUID fk coercion
- [ ] `poe lint` and `poe test:unit` pass

## Review amendments (2026-09-28)

- `coerce_column_value` moves to `st-v058-byoa-24`. This story covers only `introspect_primary_key` and `datetime_kind`, so it no longer waits for the filter work (`-19`).

## Blocked by

- `featcore-primarykeyinfo-codec-invalidprimarykey-and-baseadap` (st-v058-byoa-13)
- `featcore-timezones-module-and-settings-timezone` (st-v058-byoa-14)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
