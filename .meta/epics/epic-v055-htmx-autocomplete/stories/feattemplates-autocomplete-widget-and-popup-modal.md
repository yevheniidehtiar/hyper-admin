---
type: story
id: st-v055-ac-03
title: "feat(templates): AutocompleteWidget, popup modal, ha-popup-root slot"
status: todo
priority: high
assignee: null
labels:
  - size:M
  - planned
  - frontend
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

Replace the default `<select>` rendering for FK/M2M fields with an
`AutocompleteWidget` driven by HTMX: debounced search input, hidden
populated `<select>`, optional "+" popup button, and `hx-include` of the
`depends_on` field when one is configured. Add the single
`<div id="ha-popup-root">` slot to `base.html` and the minimal JS listener
that consumes `hyperadminPopupCreated`.

**Spec:** [`docs/specs/htmx-autocomplete.md`](../../../../docs/specs/htmx-autocomplete.md)

## Files to Change

- **New:** `src/hyperadmin/templates/widgets/autocomplete.html`
- **Modified:** `src/hyperadmin/templates/widgets/choices_options.html` — render `display_template` when configured
- **Modified:** `src/hyperadmin/templates/base.html` — add `<div id="ha-popup-root">`
- **Modified:** `src/hyperadmin/views/forms.py` — wire `AutocompleteWidget` when `use_autocomplete_widget=True`

## data-testid Reference

| Element | testid |
|---|---|
| Search input | `autocomplete-{field}` |
| Hidden select | `autocomplete-select-{field}` |
| "+" popup button | `autocomplete-add-{field}` |
| Popup modal root | `popup-root` |

## Scenarios

```
Scenario: FK field renders as autocomplete by default
  When  the user opens /admin/products/create
  Then  the supplier_id field is rendered with data-testid="autocomplete-supplier_id"

Scenario: dependent FK widget includes parent field in hx-include
  Given relation_filters has variant_id depends_on supplier_id
  When  the widget for variant_id is rendered
  Then  its hx-include attribute is "[name='supplier_id']"

Scenario: "+" button omitted when related model unregistered
  Given Supplier is NOT registered with the Admin
  When  the supplier_id widget renders
  Then  no element with data-testid="autocomplete-add-supplier_id" is present

Scenario: display_template renders custom option label
  Given relation_display has supplier_id = "{name} — {city}"
  And   the dataset has one Supplier(name="Acme", city="Paris")
  When  choices_view returns a fragment
  Then  the rendered option label is "Acme — Paris"
```

## Acceptance Criteria

- [ ] `AutocompleteWidget` rendered for FK/M2M when `use_autocomplete_widget=True`
- [ ] `hx-include` is set when `depends_on` is configured
- [ ] "+" button only rendered when related model is in `Admin.registry`
- [ ] `display_template` format-string applied in `choices_options.html`
- [ ] `<div id="ha-popup-root">` present once in `base.html`
- [ ] Minimal inline JS listener inserts new option + closes modal
- [ ] All four scenarios covered by unit or rendering tests
- [ ] `poe lint` passes

## Blocked by

- `featviews-add-create-popup-view`

## Parent

- Epic: `epic-v055-htmx-autocomplete`
