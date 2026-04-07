---
type: story
id: nXOi7g8Yr_7x
title: "feat(views): dependent (cascading) select endpoint and widget support"
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
  issue_number: 166
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:971b962a5304ede3e93e07d22f8efc8d7829baeb678068919776e28c05cad2a5
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:38:22Z
updated_at: 2026-03-26T23:50:45Z
---

> **Part of:** #159
> **Depends on: #165**

## Context

Some selects must filter their choices based on a sibling field's value (e.g. City filtered by Country).
The same `get_choices` endpoint from #165 must accept additional `**filter` kwargs,
and the widget must emit the correct HTMX trigger when the parent field changes.

## Acceptance Criteria

- [ ] `GET /admin/{model}/choices/{field}?q=&{parent_field}={value}` — existing endpoint extended:
  - Extra query params forwarded as `**filters` to `adapter.get_choices()`
  - Adapter applies them as WHERE clauses (e.g. `WHERE city.country_id = :value`)
- [ ] `RelationSelectWidget` and `RelationMultiSelectWidget` accept optional `dependent_on: str | None`:
  - When set, HTMX trigger includes `hx-include="[name={dependent_on}]"` so the parent value is sent
  - Widget emits `hx-trigger="change from:[name={dependent_on}]"` to refresh on parent change
- [ ] `SelectFieldMeta.dependent_on` wired to widget construction in `DynamicModelView`
- [ ] Configurable via `ModelAdmin.dependent_fields: dict[str, str]` (child → parent)
- [ ] Unit tests: mock adapter asserting filter kwargs are forwarded
- [ ] E2E test: changing parent select refreshes child options

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/core/options.py` (add `dependent_fields` option)
- `src/hyperadmin/templates/widgets/relation_select_input.html`
- `tests/unit/test_dependent_select.py` (new)

## Dependencies

Depends on: #165

## Notes for Implementer

`hx-include` must be a CSS selector pointing to the parent field: `[name=country_id]`.
When the parent field is cleared/empty, child select should also clear — handle via `hx-trigger="change"` with an empty q.
