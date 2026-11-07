---
type: story
id: st-ux-erp-18
title: "fix(templates): Permission matrix empty state offers to create a group"
status: backlog
priority: low
assignee: null
labels:
  - planned
  - enhancement
  - ui
  - area:templates
  - area:auth
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:13.122Z
updated_at: 2026-11-07T07:21:13.122Z
---

## Summary

With no groups the matrix says "Create a group first" but has no button to do it, and an empty Group select sits above it.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Access → Permission matrix with the ERP seed.

## Files to Change

- **Modified:** `src/hyperadmin/templates/permissions/matrix.html`

## Scenarios

```
Scenario: empty state has a next step
  Given no groups exist
  Then  the matrix shows a "Create group" button and no Group select
```

## Acceptance Criteria

- [ ] Button respects add-group permission

