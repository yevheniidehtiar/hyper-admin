---
type: story
id: xtGoFKkfxC7P
title: "feat(ui): responsive login, detail, and dashboard views"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - ui
  - size:S
  - planned
  - responsive
  - wave:3
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: 470
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:20172ef1f88568a37bfdf935682a5fce71383f0c257757ec1bda99f37028f1e5
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:46:00Z
updated_at: 2026-04-01T21:46:01Z
---

## Summary

Ensure remaining views (login, detail, dashboard) are fully responsive. Login card centered and usable, detail fields stack, action buttons wrap.

## Scenarios

**Scenario: login page is centered and usable on mobile**
  Given viewport width is 375px
  When  the login page loads
  Then  the login card is centered vertically and horizontally
  And   inputs are full-width with adequate touch targets
  And   the Sign In button is full-width

**Scenario: detail view is readable on mobile**
  Given viewport width is 375px
  When  a detail view loads
  Then  field labels and values stack vertically
  And   action buttons wrap to avoid horizontal overflow
  And   the "Back to list" link has adequate touch target

## Acceptance criteria

- [ ] Login page centered and usable at 375px
- [ ] Detail view readable at 375px with stacked fields and wrapping actions

## Files to modify

- `src/hyperadmin/static/css/_login.css` — verify/adjust mobile padding
- `src/hyperadmin/static/css/_buttons.css` — ensure `.ha-action-buttons` wraps on mobile
- `src/hyperadmin/static/css/_responsive.css` — detail view and dashboard mobile rules

## Implementation notes

- Login card already has `max-width: 24rem` — may need reduced padding at very small screens
- Detail view `.ha-form-group` labels and values already stack; main concern is action buttons overflowing
- Use `flex-wrap: wrap` on `.ha-action-buttons`

## Demo checkpoint

At 375px viewport:
1. Login page: card centered, inputs full-width, Sign In button full-width
2. Detail view: field labels and values stacked vertically, action buttons wrap
3. Widen to 1024px -- standard desktop layout restored

## Agent

- **Size:** S
- **Tier:** Sonnet
- **blocked_by:** W2-A (8P_VPRTVAWHF), W2-B (KKpriYWS0U9B) — needs sidebar + table responsive to exist
