---
type: epic
id: ep-v055-ac-01
title: "epic(views): HTMX FK/M2M autocomplete with dependent filtering and inline create"
status: todo
priority: high
owner: null
labels:
  - size:L
  - planned
  - backend
  - frontend
  - upstream-readiness
  - H6
milestone_ref:
  id: v055-bulk-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Overview

Implements upstream readiness capability **H6**: declarative dependent FK/M2M
filtering, a "+" popup that creates the related row without losing parent-form
state, and per-relation `display_template` for option rendering. Backward
compatible — existing relation widgets keep working unchanged.

**SDD:** [`docs/specs/htmx-autocomplete.md`](../../../docs/specs/htmx-autocomplete.md)
(required — touches `core/`, `views/`, `templates/widgets/`).

## Tracks

### Track A: Options + field metadata
- `AdminOptions.relation_filters: dict[str, RelationDependency] | None`.
- `AdminOptions.relation_display: dict[str, str] | None`.
- `RelationDependency` Pydantic model (`depends_on`, `placeholder`).
- Validation: `depends_on` must reference an existing form field on the same model.

### Track B: Popup endpoint + widget
- `DynamicModelView.create_popup_view` — POST `/{model}/create-popup`.
- On success: `HX-Trigger: hyperadminPopupCreated` with `{id, label, target}`.
- `AutocompleteWidget` rendered for FK/M2M when `use_autocomplete_widget=True`
  (default True in v0.5.5).

### Track C: Templates + JS glue
- `templates/widgets/autocomplete.html` — search input, hidden select, popup button.
- `templates/widgets/popup_form.html` — modal shell, returns empty body + HX-Trigger.
- Single `<div id="ha-popup-root">` in `base.html` for modal swap target.
- Tiny inline JS listener that consumes `hyperadminPopupCreated`, inserts the
  new option into the target select, and closes the modal. No new bundled JS file.

## Scenarios

(See SDD for the full set; seven scenarios listed under `## BDD Scenarios`.)

## Acceptance Criteria

- [ ] `AdminOptions.relation_filters` / `relation_display` configurable
- [ ] `RelationDependency.depends_on` validated against form fields
- [ ] FK fields render as `AutocompleteWidget` by default
- [ ] Dependent FK forwards parent value via `hx-include`
- [ ] Dropdown empty + placeholder shown when parent is unset
- [ ] "+" button renders only when the related model is registered with the same Admin
- [ ] Popup success returns `HX-Trigger: hyperadminPopupCreated` with payload
- [ ] `display_template` format strings render custom option labels
- [ ] `choices_view` returns 404 for unknown relation field (regression test)
- [ ] Unit tests for options validation, widget rendering, popup view
- [ ] E2E tests for all seven scenarios
- [ ] `poe lint` and `poe test` pass

## Blocked by

- `reviewspec-approve-sdd-htmx-autocomplete` (SDD approved)

## Parent

- Milestone: `v055-bulk-actions-autocomplete`
- Tracking: `epic-upstream-readiness` (H6)
