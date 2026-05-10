---
type: story
id: st-v055-ac-01
title: "feat(core): extend AdminOptions with relation_filters and relation_display"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - backend
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Add the two declarative knobs that drive dependent filtering and custom option
labels. Validate `depends_on` against the model's form fields at construction.

**Spec:** [`docs/specs/htmx-autocomplete.md`](../../../../docs/specs/htmx-autocomplete.md)

## Files to Change

- **Modified:** `src/hyperadmin/core/options.py` — add `relation_filters`, `relation_display`, `use_autocomplete_widget` (default True), `RelationDependency` model
- **Modified:** `tests/unit/test_options.py` (new file if absent) — validation tests

## Scenarios

```
Scenario: relation_filters with unknown depends_on raises at construction
  Given AdminOptions(relation_filters={"variant_id": {"depends_on": "missing"}})
  When  the options are bound to a model with no "missing" field
  Then  ValueError is raised: "depends_on='missing' not in form fields"

Scenario: relation_display format string with valid placeholder is accepted
  Given AdminOptions(relation_display={"supplier_id": "{name} — {city}"})
  When  the options are validated against Supplier
  Then  no error is raised
```

## Acceptance Criteria

- [ ] `RelationDependency` Pydantic model in `core/options.py`
- [ ] `AdminOptions.relation_filters`, `relation_display`, `use_autocomplete_widget` added
- [ ] Construction-time validation of `depends_on` against form fields
- [ ] `use_autocomplete_widget` defaults to True
- [ ] Unit tests for validation
- [ ] `poe lint` passes

## Blocked by

- `reviewspec-approve-sdd-htmx-autocomplete`

## Parent

- Epic: `epic-v055-htmx-autocomplete`
