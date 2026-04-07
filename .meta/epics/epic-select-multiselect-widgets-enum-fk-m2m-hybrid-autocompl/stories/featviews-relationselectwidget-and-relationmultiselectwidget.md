---
type: story
id: aQpFqn0bVdEy
title: "feat(views): RelationSelectWidget and RelationMultiSelectWidget with preload strategies"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 164
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b42f08300da0f0b8caf2f96e3a64e0cd7cee746ff7dd4e65575b378c4675ef6d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:37:34Z
updated_at: 2026-03-26T23:50:52Z
---

> **Part of:** #159
> **Depends on: #161, #162**

## Context

FK and M2M fields need widgets that fetch their choices from the adapter.
Two loading strategies must be supported:
- **Preload** (`preload=True`): choices fetched server-side at render time, baked into the page HTML
- **Lazy** (`preload=False`): empty `<select>` rendered, choices loaded via HTMX on focus/type (see #166)

## Acceptance Criteria

- [ ] `RelationSelectWidget(HtmxWidget)` in `views/forms.py`:
  - `preload: bool`, `choices_url: str` (HTMX endpoint for lazy mode)
  - When `preload=True`: `choices: list[ChoiceItem]` injected at construction; renders full select
  - When `preload=False`: renders minimal placeholder; HTMX attrs point to autocomplete endpoint
  - Template: `widgets/relation_select_input.html`
- [ ] `RelationMultiSelectWidget(HtmxWidget)` — same strategy, `multiple=True`
  - Template: `widgets/relation_multiselect_input.html`
- [ ] `DynamicModelView` creates these widgets in `create_form_view()` / `update_form_view()`:
  - Calls `adapter.get_choices(field, preload=True)` for preloaded fields
  - Skips DB call for lazy fields (choices fetched client-side)
- [ ] No N+1: preload calls are batched per field, not per record
- [ ] Unit tests with mocked adapter asserting correct choices and HTMX attrs

## Files Likely Affected

- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/templates/widgets/relation_select_input.html` (new)
- `src/hyperadmin/templates/widgets/relation_multiselect_input.html` (new)
- `tests/unit/test_forms.py`

## Dependencies

Depends on: #161, #163

## Notes for Implementer

When `preload=False`, the widget must still emit the currently selected value(s) so the form re-renders correctly on validation failure — fetch only the selected record(s) by PK, not the full list.
HTMX attrs: `hx-get="{choices_url}?q="`, `hx-trigger="focus delay:200ms, input changed delay:300ms"`, `hx-target="#{field_name}-options"`.
