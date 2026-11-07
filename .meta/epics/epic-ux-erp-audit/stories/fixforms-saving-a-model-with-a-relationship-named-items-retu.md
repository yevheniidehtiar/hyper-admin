---
type: story
id: st-ux-erp-01
title: "fix(forms): saving a model with a relationship named `items` returns 500"
status: backlog
priority: critical
assignee: null
labels:
  - planned
  - bug
  - forms
  - area:views
  - backend
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:04.191Z
updated_at: 2026-11-07T07:21:04.191Z
---

## Summary

Every create and edit of an ERP `Invoice` or `Bill` fails. `ModelForm.validate` passes a plain dict to `schema_for(model).model_validate(...)`; for the `Invoice.items` / `Bill.items` relationship SQLModel reads `getattr(data, "items")`, gets the dict's own `.items` method and assigns it to the relationship.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- 15 invoice edits: 8 × HTTP 500, 7 × 422 (the other 7 hit the FK-preload bug). Invoice create → 500. Bill edit → 500 (4/4). Contact edit → 200.
- Traceback: `views/forms.py:743 validate` → `sqlmodel/_compat.py sqlmodel_validate` → `TypeError: Incompatible collection type: builtin_function_or_method is not list-like`.

## Files to Change

- **Modified:** `src/hyperadmin/views/forms.py` (`ModelForm.validate`: validate without relationship attributes, or validate an object/namespace instead of a dict)
- **New:** unit test with a model whose relationship is named `items` (also `keys`, `values`)

## Scenarios

```
Scenario: invoice edit saves
  Given the ERP example and invoice 3 with its customer selected
  When  the user changes the number and clicks Update
  Then  the response is not 5xx and the new number is shown after a reload

Scenario: invoice create saves with one line item
  Given the create form filled with number, dates, customer and one item
  When  the user clicks Create
  Then  the invoice appears in the list
```

## Acceptance Criteria

- [ ] Create and edit of `Invoice` and `Bill` in `examples/erp` succeed
- [ ] Unit test covers a relationship named `items`, `keys` and `values`
- [ ] E2E test edits and creates an ERP invoice

