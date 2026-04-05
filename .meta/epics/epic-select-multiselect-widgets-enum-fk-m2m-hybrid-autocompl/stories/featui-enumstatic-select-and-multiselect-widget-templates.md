---
type: story
id: 2T6E--wCxBXN
title: "feat(ui): enum/static select and multiselect widget templates"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 169
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b0b5a08867dbcf1f7969f135426466452d31c399eaa2132e816597d6223df503
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:39:23Z
updated_at: 2026-03-26T23:50:09Z
---

> **Part of:** #159
> **Depends on: #163**

## Context

The `SelectWidget` and `MultiSelectWidget` from #163 need Jinja2 templates.
The existing `select_input.html` can be updated for the new `SelectWidget`.
A new `multiselect_input.html` is needed for multiple-choice static fields (e.g. list[str] hybrid, list[Enum]).

## Acceptance Criteria

- [ ] `templates/widgets/select_input.html` updated:
  - Iterates `field.widget.choices` (list of `ChoiceItem`) instead of `field.model_field.annotation` enum members
  - Backward-compatible: if `choices` is empty falls back gracefully
  - Includes `data-testid="{field.name}-select"`
- [ ] `templates/widgets/multiselect_input.html` (new):
  - `<select multiple name="{field.name}" id="{field.name}">`
  - Iterates choices, marks selected correctly
  - Accessible: `<label>` linked, `aria-multiselectable="true"`
  - Error display block with `data-testid="{field.name}-errors"`
  - CSS classes: `ha-multiselect`, `ha-form-group`, `ha-label`
- [ ] Visual consistency with existing widgets (same ha-* class structure)
- [ ] Manual smoke test: enum field renders single select; list[str] hybrid renders multiselect

## Files Likely Affected

- `src/hyperadmin/templates/widgets/select_input.html`
- `src/hyperadmin/templates/widgets/multiselect_input.html` (new)

## Dependencies

Depends on: #163

## Notes for Implementer

No JS required for static lists — pure HTML `<select multiple>` is sufficient.
For Enum choices, `ChoiceItem.value` is the enum's `.value`; `ChoiceItem.label` is the enum's `.name` (human-readable).
