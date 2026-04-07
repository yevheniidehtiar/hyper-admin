---
type: story
id: l-uEZa6gW4D7
title: "feat(ui): dependent cascading select UI component"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref:
  id: -TGq_yaQZtX_
github:
  issue_number: 171
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:339ec82b005b4e6ed1c819b649ce30d05fc793e25d8f565814f659eb282a1818
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-20T15:39:55Z
updated_at: 2026-03-28T17:45:41Z
---

> **Part of:** #159
> **Depends on: #166, #170**

## Context

When a select field depends on another (`dependent_on` from #166), the child select must:
1. Clear and reload its options when the parent changes
2. Show a "Select {parent} first" placeholder when parent is empty
3. Pass the parent's current value as a query param to the choices endpoint

## Acceptance Criteria

- [ ] `relation_select_input.html` updated for dependent mode:
  - When `widget.dependent_on` is set:
    - `hx-include="[name={{ widget.dependent_on }}]"` added to the child select element
    - `hx-trigger` includes `"change from:[name={{ widget.dependent_on }}]"` to auto-refresh
    - Placeholder `<option disabled selected>Select {parent_label} first</option>` shown when parent empty
  - `data-testid="{field.name}-dependent-select"`
- [ ] `relation_multiselect_input.html` same dependent-mode support
- [ ] CSS: visual "disabled" state when parent has no value (use `ha-select--disabled` class)
- [ ] E2E test: changing parent clears child and fetches filtered options
- [ ] E2E test: submitting form with cascaded selection saves correctly

## Files Likely Affected

- `src/hyperadmin/templates/widgets/relation_select_input.html`
- `src/hyperadmin/templates/widgets/relation_multiselect_input.html`
- `src/hyperadmin/static/css/` (ha-select--disabled class)
- `tests/e2e/test_dependent_select.py` (new)

## Dependencies

Depends on: #166, #170

## Notes for Implementer

The HTMX `hx-include` selector must target by `name` attribute, not `id`, to work with any form layout.
When parent value is empty string, the child endpoint should return an empty options list — the adapter's `get_choices(filters={"parent_id": ""})` should handle this gracefully (return `[]`).
