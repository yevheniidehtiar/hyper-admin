---
type: epic
id: epic-inline-cell-editing
title: "Epic: Inline Cell Editing in List View (v0.5.0 close-out)"
status: in-progress
priority: medium
owner: claude-code
labels:
  - enhancement
  - frontend
  - ui
  - htmx
milestone_ref:
  id: YONrzO1hQ2f8
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Epic: Inline Cell Editing in List View

Part of milestone: **v0.5.0 — Advanced UX**

### Goal

Add Django-style `list_editable` inline cell editing to the admin list view.
Closes the last open scope item from milestone v0.5.0 (UI polish, themes,
WCAG, **inline model editing**).

**Spec**: [docs/specs/inline-cell-editing.md](../../../docs/specs/inline-cell-editing.md)

### Bottom-up implementation order

```
core/options.py     — add list_editable allow-list
   └─ adapters      — reuse existing update(pk, data)
        └─ views    — new inline_edit_form_view + inline_save_view
             └─ routing — register GET + POST per model
                  └─ templates — inline_cell.html + inline_editor.html + error fragment
                       └─ static/css — minimal styling
                            └─ tests/unit + tests/e2e — BDD scenarios
```

### Sub-issues / stories

- [ ] task-1: Domain — `list_editable` option on `AdminOptions` + ModelAdmin wiring
- [ ] task-2: Views — inline edit form view + inline save view (with permission gate)
- [ ] task-3: Routing — register `/inline/{field}` GET + POST per model
- [ ] task-4: Templates — `inline_cell.html`, `inline_editor.html`, `inline_cell_error.html`, table integration
- [ ] task-5: Static — minimal CSS for inline editor states
- [ ] task-6: Tests — unit tests for views + adapter integration
- [ ] task-e2e: E2E — Playwright tests, one per BDD scenario
