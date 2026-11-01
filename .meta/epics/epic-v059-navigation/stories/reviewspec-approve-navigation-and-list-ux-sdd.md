---
type: story
id: st-v059-nav-00
title: "review(spec): approve navigation and list UX SDD"
status: todo
priority: critical
assignee: null
labels:
  - size:S
  - planned
  - area:docs
  - layer:gate
  - needs-human
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

**Human gate.** Review and approve the Navigation & List UX design doc before any implementation story starts. Answer the Open Questions (milestone position, palette empty-state create, `MAX_PINS`) or accept the proposals, then set the SDD status to `Approved`.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- docs/specs/navigation-and-list-ux.md

## Acceptance Criteria

- [ ] Goals and non-goals match the owner's request (groups, icons, pins, palette, compact rows, icon delete with confirm) and the chosen extras (form safety, keyboard)
- [ ] Owner decisions recorded: pins in a DB table, palette over nav entries only
- [ ] Module boundaries comply with CONSTITUTION §1/§2 (`core/navigation.py` pure; pins in their own package)
- [ ] Red-icon delete vs design-system danger rule resolved as in the Decision Log
- [ ] Story order and `Blocked by` graph accepted
- [ ] SDD `Status` set to `Approved`

## Blocked by

- none

## Parent

- Epic: `epic-v059-navigation`
