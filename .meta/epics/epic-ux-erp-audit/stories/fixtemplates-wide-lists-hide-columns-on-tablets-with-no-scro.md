---
type: story
id: st-ux-erp-08
title: "fix(templates): wide lists hide columns on tablets with no scroll hint"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - bug
  - responsive
  - area:templates
  - frontend
  - size:M
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:07.879Z
updated_at: 2026-11-07T07:21:07.879Z
---

## Summary

At 768px the invoice list is cut after "Date Due": Status, Total Amount and Delete are off-screen and nothing shows the table scrolls. Journal lines clip the delete column at the edge.

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Tablet portrait captures of `/admin/invoice` and `/admin/journalline`.

## Files to Change

- **Modified:** `src/hyperadmin/static/css/_table.css`, `_responsive.css` (card layout or column priority below `--ha-bp-lg`, scroll shadow)
- **Modified:** `src/hyperadmin/templates/components/table.html`

## Scenarios

```
Scenario: all columns reachable on a tablet
  Given a 768x1024 viewport and the invoice list
  Then  Status and Total Amount are visible without horizontal scrolling
  Or    the table shows a visible scroll shadow on the right edge
```

## Acceptance Criteria

- [ ] No silently clipped columns between 768 and 1023px
- [ ] Visual baselines refreshed

