---
type: story
id: 15CEiBOvAi6d
title: "feat(examples): responsive design showcase in demo app"
status: todo
priority: low
assignee: null
labels:
  - frontend
  - examples
  - size:S
  - responsive
  - cycle:3
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Add a section to the example app README documenting the responsive capabilities.
Ensure the ERP example app exercises all responsive features: list with many columns
(triggers card layout), forms with fieldsets (triggers stacked layout), dashboard widgets.

## Scenarios

**Scenario: ERP example app list view shows card layout on mobile**
  Given the ERP example app is running
  When  opening the contacts list at 375px viewport
  Then  contacts display as stacked cards

**Scenario: ERP example app form collapses to single column on mobile**
  Given the ERP example app is running
  When  opening a contact create form at 375px viewport
  Then  form fields display in single column

## Acceptance criteria

- [ ] ERP example exercises card layout, sidebar toggle, mobile forms
- [ ] README documents responsive features

## Files to modify

- `examples/erp/README.md` — add responsive section
- `examples/erp/app.py` — ensure list_display has enough columns to trigger card mode

## Demo checkpoint

Run `python examples/erp/app.py`, open in mobile-sized browser, verify card layout on list.

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** all Cycle 2 stories (C2-A, C2-B, C2-C, C2-D)
