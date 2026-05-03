---
type: story
id: ice-task-5
title: "Task 5: Minimal CSS for inline editor states"
status: in-progress
priority: low
labels:
  - task
  - css
estimate: S
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Append to `src/hyperadmin/static/css/hyperadmin.css`:

- `.ha-cell-edit` — small button affordance inside read-only cell
- `.ha-inline-editor` — wrapper for the inline form fragment
- `.ha-inline-editor input` — full-width compact input
- `.ha-inline-actions` — Save/Cancel button row
- `.ha-cell-saved` — short-lived "saved" highlight
- Respect existing CSS custom properties / dark mode

## Acceptance Criteria

- [ ] No new framework dependency
- [ ] Theme-aware via existing CSS custom properties
- [ ] Mobile/responsive friendly
