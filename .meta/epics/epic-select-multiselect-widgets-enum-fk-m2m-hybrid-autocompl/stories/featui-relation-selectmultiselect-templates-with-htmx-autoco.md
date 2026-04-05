---
type: story
id: 3MHi0m9YIAWt
title: "feat(ui): relation select/multiselect templates with HTMX autocomplete"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 170
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:65769a3911b3bd20b1c69fb5d2d765f8684892a698be849914fec51647ee1f11
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:39:41Z
updated_at: 2026-03-26T23:50:02Z
---

> **Part of:** #159
> **Depends on: #164, #165**

## Context

`RelationSelectWidget` and `RelationMultiSelectWidget` from #164 need templates that handle
two rendering modes: preloaded (choices in HTML) and lazy (HTMX-driven autocomplete).
The lazy mode uses a search input + HTMX to fetch `<option>` fragments from the endpoint in #165.

## Acceptance Criteria

- [ ] `templates/widgets/relation_select_input.html` (new):
  - **Preload mode**: renders `<select>` with all choices as `<option>` tags
  - **Lazy mode**: renders `<input type="search">` + empty `<select>` with HTMX attrs:
    - `hx-get="{widget.choices_url}?q="`, `hx-trigger="input changed delay:300ms, focus"`, `hx-target="#{field.name}-options"`, `hx-swap="innerHTML"`
  - Hidden `<input type="hidden" name="{field.name}">` updated by JS on selection (for single-select lazy)
  - `data-testid="{field.name}-relation-select"`
- [ ] `templates/widgets/relation_multiselect_input.html` (new):
  - Lazy: HTMX-driven `<select multiple>` with search input above it
  - Selected items shown as removable tags (pure CSS, no external lib)
  - `data-testid="{field.name}-relation-multiselect"`
- [ ] `templates/widgets/choices_options.html` (new, fragment):
  - Just `<option>` tags — no wrapper — for HTMX `innerHTML` swap
- [ ] `static_list` on widgets declares any minimal JS needed (prefer vanilla JS <50 LOC over external libs)
- [ ] E2E: relation field lazy → type 2 chars → dropdown populates (from #165 endpoint)

## Files Likely Affected

- `src/hyperadmin/templates/widgets/relation_select_input.html` (new)
- `src/hyperadmin/templates/widgets/relation_multiselect_input.html` (new)
- `src/hyperadmin/templates/widgets/choices_options.html` (new)
- `src/hyperadmin/static/` (minimal JS if needed)
- `tests/e2e/test_relation_select.py`

## Dependencies

Depends on: #164, #165

## Notes for Implementer

Avoid pulling in tom-select, Select2, or Choices.js as runtime deps — keep the library footprint minimal.
A small vanilla-JS snippet (< 50 LOC) to update the hidden input on option click is acceptable and preferred.
The search input is decorative (for UX) — the actual form value must come from `<select>` or `<input type="hidden">`, not the text input.
