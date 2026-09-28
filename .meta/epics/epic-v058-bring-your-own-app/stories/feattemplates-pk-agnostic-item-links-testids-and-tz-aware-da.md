---
type: story
id: st-v058-byoa-45
title: "feat(templates): pk-agnostic item links/testids and tz-aware datetime rendering"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - area:templates
  - layer:ui
  - frontend
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Replace `item.id` with `item|ha_pk(pk_attr)` in URLs and with `|ha_dom_token` in ids and testids. Display cells use `|ha_display`. The `datetime_input` widget uses `|ha_datetime_input`, `step=1` and a timezone hint (`data-testid='{field}-tz'`). Refresh the affected visual baselines.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.9

## Files to Change

- `src/hyperadmin/templates/components/table.html`
- `src/hyperadmin/templates/components/inline_cell.html`
- `src/hyperadmin/templates/components/inline_editor.html`
- `src/hyperadmin/templates/components/inline_cell_error.html`
- `src/hyperadmin/templates/update.html`
- `src/hyperadmin/templates/detail.html`
- `src/hyperadmin/templates/components/bulk_form.html`
- `src/hyperadmin/templates/components/bulk_result.html`
- `src/hyperadmin/templates/widgets/datetime_input.html`

## Scenarios

```
Scenario: int-id links unchanged
  Given an int-id Product with id 7
  When  the list renders
  Then  the View href is /admin/product/7
  And   the edit testid is cell-edit-name-7

Scenario: UUID links work
  Given a UUID Document
  When  View, Edit and Delete are followed
  Then  each page returns 200

Scenario: aware edit value
  Given an aware starts_at
  When  the edit form renders
  Then  the input value is display-tz ISO with seconds and step=1

Scenario: aware list cell
  Given an aware datetime column
  When  the list renders
  Then  a <time> element with a UTC ISO datetime attribute is shown
```

## Acceptance Criteria

- [ ] int-id links unchanged
- [ ] UUID links work
- [ ] aware edit value
- [ ] aware list cell
- [ ] `poe lint` and `poe test:unit` pass (and `poe test:e2e`)

## Review amendments (2026-09-28)

- Also cover `components/bulk_result.html` (19, 22, 33; `ha_dom_token` for the `outcome.id` testid), `components/bulk_form.html:17-18`, and `components/inline_row.html:10`: `{% if row.pk is not none %}` instead of the truthy check.
- `detail.html:14` links files through the per-record route `<model>-file` (`-37`).

## Blocked by

- `featforms-tz-aware-datetime-parsing-aware-naivedatetime-widg` (st-v058-byoa-32)
- `featviews-template-filters-ha-pk-ha-dom-token-ha-datetime-in` (st-v058-byoa-33)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
