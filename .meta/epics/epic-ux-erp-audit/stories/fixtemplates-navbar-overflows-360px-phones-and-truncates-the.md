---
type: story
id: st-ux-erp-05
title: "fix(templates): navbar overflows 360px phones and truncates the brand"
status: backlog
priority: high
assignee: null
labels:
  - planned
  - bug
  - responsive
  - area:templates
  - frontend
  - size:S
estimate: null
epic_ref:
  id: ep-ux-erp-01
created_at: 2026-11-07T07:21:06.289Z
updated_at: 2026-11-07T07:21:06.289Z
---

## Summary

Since the command-palette trigger landed, the navbar actions are 10px wider than a 360px screen, so every page scrolls sideways and the account menu arrow is clipped. At 393px the brand name is cut to a single "I".

Found by the UI/UX audit of `examples/erp` on `develop` @ `0014cc1` (2026-11-06): 51 pages × 6 devices (360/393 phone, 768/1180 tablet, 1280 laptop, 1920 desktop) × light/dark.

## Evidence

- Automated check: `horizontal-scroll` on 51/51 pages at 360×740 (`ha-navbar-actions` spans 96–370px).
- 393px: brand renders as logo + "I".

## Files to Change

- **Modified:** `src/hyperadmin/templates/_navbar.html`, `src/hyperadmin/static/css/_navbar.css`

## Scenarios

```
Scenario: no horizontal scroll on a small phone
  Given a 360x740 touch viewport
  When  any admin page loads
  Then  document scrollWidth equals the viewport width

Scenario: brand is not truncated to one letter
  Given a 393x852 viewport
  Then  the navbar shows the logo only, with the site name as its accessible label
```

## Acceptance Criteria

- [ ] Language and theme controls move into the account menu below `--ha-bp-sm`
- [ ] E2E responsive test asserts no horizontal scroll at 360px

