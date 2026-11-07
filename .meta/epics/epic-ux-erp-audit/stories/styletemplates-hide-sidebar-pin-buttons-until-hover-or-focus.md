---
type: story
id: st-ux-erp-16
title: "style(templates): hide sidebar pin buttons until hover or focus"
status: backlog
priority: low
assignee: null
labels:
  - planned
  - enhancement
  - ui
  - area:templates
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:12.070Z
updated_at: 2026-11-07T07:21:12.070Z
---

## Summary

The phone menu shows a pin icon on every item: 12+ identical icons compete with the labels.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Phone menu open on `/admin/invoice`.

## Files to Change

- **Modified:** `src/hyperadmin/templates/components/_nav.html`, `src/hyperadmin/static/css/_sidebar.css`

## Scenarios

```
Scenario: pins appear on demand
  Given the sidebar
  Then  a pin button is visible only on the hovered or focused item and on already-pinned items
```

## Acceptance Criteria

- [ ] Pinning stays reachable by keyboard and touch

