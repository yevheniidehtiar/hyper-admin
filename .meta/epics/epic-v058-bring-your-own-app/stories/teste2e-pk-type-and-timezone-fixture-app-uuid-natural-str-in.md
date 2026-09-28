---
type: story
id: st-v058-byoa-49
title: "test(e2e): pk-type and timezone fixture app (UUID, natural str, int)"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:tests
  - layer:ui
  - e2e
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add a dedicated fixture app at `tests/e2e/apps/pk_types.py` (this keeps `examples/simple` baselines stable) with Playwright coverage that uses only role, label, text and test-id locators.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: BDD Scenarios: Keys, Datetimes

## Files to Change

- `tests/e2e/apps/pk_types.py`
- `tests/e2e/test_pk_types.py`
- `tests/e2e/test_datetime_tz.py`
- `tests/e2e/conftest.py`

## Scenarios

```
Scenario: UUID CRUD
  Given a UUID model
  When  the user views, edits and deletes a row via row-view-link, row-edit-link, row-delete-btn
  Then  each step succeeds

Scenario: malformed UUID
  Given the fixture app
  When  GET /admin/document/not-a-uuid is requested
  Then  the status is 404

Scenario: natural key create
  Given a str-pk model
  When  the user creates code 'NL'
  Then  the detail page for NL opens

Scenario: UUID inline edit
  Given list_editable on the UUID model
  When  the user inline-edits a cell
  Then  the cell-saved flag appears

Scenario: timezone round-trip
  Given HYPERADMIN_TIMEZONE=Europe/Amsterdam
  When  the user enters 10:00
  Then  the list shows 10:00
  And   the DB holds 08:00Z
```

## Acceptance Criteria

- [ ] UUID CRUD
- [ ] malformed UUID
- [ ] natural key create
- [ ] UUID inline edit
- [ ] timezone round-trip
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Blocked by

- `refactorviews-bulk-ids-single-actions-and-popup-payload-are` (st-v058-byoa-30)
- `feattemplates-pk-agnostic-item-links-testids-and-tz-aware-da` (st-v058-byoa-45)
- `builddeps-lift-the-sqlmodel-0-0-45-cap-and-migrate-examples` (st-v058-byoa-48)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
