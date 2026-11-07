---
type: story
id: st-ux-erp-09
title: "fix(css): 44px touch targets for sidebar group toggles, pin buttons and sort links"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - bug
  - accessibility
  - responsive
  - css
  - area:templates
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:08.393Z
updated_at: 2026-11-07T07:21:08.393Z
---

## Summary

Under `pointer: coarse` the new sidebar group toggles (28px), pin buttons (28px), rail toggle (36px) and list sort links (24px) stay below the 44px touch target. They are missing from the coarse-pointer list in `_accessibility.css`.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Automated `tap-target` findings on tablet/phone: `ha-nav-group__toggle` 175×28, `nav-pin-*` 28×28, `sidebar-rail-toggle` 36×36, `sort-*` ×24.

## Files to Change

- **Modified:** `src/hyperadmin/static/css/_accessibility.css`

## Scenarios

```
Scenario: navigation controls are touch-sized
  Given a touch device (pointer: coarse)
  Then  sidebar group toggles, pin buttons, the rail toggle and sort links are at least 44px tall
```

## Acceptance Criteria

- [ ] Extend the existing E2E touch-target test with these controls

