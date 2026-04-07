---
type: story
id: Rsp4_skel_04
title: "feat(ui): HTMX loading skeleton states for mobile"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - ui
  - size:M
  - planned
  - responsive
estimate: null
epic_ref: Rsp4_Gamma_01
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Add CSS skeleton loading indicators during HTMX swaps on mobile. On slower mobile connections, HTMX swaps can leave the user staring at stale content with no feedback. Add a pulsing skeleton placeholder that appears during list view searches, filter changes, pagination, and sort operations.

## Scenarios

**Scenario: skeleton placeholder appears during HTMX list swap**
  Given viewport width is 375px and the list view is loaded
  When  the user types in the search input (triggering hx-get)
  Then  the table area shows a pulsing skeleton placeholder
  And   the skeleton disappears when the new content loads

**Scenario: skeleton shows during pagination swap**
  Given viewport width is 375px and the list view has multiple pages
  When  the user taps the Next page button
  Then  a skeleton placeholder replaces the card list while loading
  And   the new page content replaces the skeleton

**Scenario: skeleton respects reduced-motion preference**
  Given the user has prefers-reduced-motion enabled
  When  an HTMX swap triggers the skeleton
  Then  the skeleton displays as a static gray placeholder without animation

**Scenario: skeleton loading state is announced to screen readers**
  Given a screen reader is active and the list view is loaded
  When  an HTMX swap triggers the skeleton placeholder
  Then  the skeleton container has aria-busy="true" and role="status"
  And   a visually hidden "Loading..." text is announced
  And   when content loads, aria-busy is set to "false"

## Acceptance criteria

- [ ] Skeleton placeholder visible during HTMX list swaps
- [ ] Skeleton appears for search, filter, pagination, and sort triggers
- [ ] Skeleton respects prefers-reduced-motion
- [ ] Skeleton uses pure CSS (no JavaScript, no new deps)
- [ ] Skeleton container announces loading state to screen readers via aria-busy

## Files to modify

- `src/hyperadmin/static/css/_table.css` -- add `.ha-skeleton` pulse animation
- `src/hyperadmin/static/css/_accessibility.css` -- reduce motion skeleton variant
- `src/hyperadmin/templates/components/table.html` -- add hx-indicator skeleton element
- `src/hyperadmin/templates/list_layout.html` -- wire hx-indicator to skeleton

## Implementation notes

- Use HTMX `hx-indicator` attribute pointing to a `.ha-skeleton` div
- Skeleton CSS: `background: linear-gradient(90deg, var(--ha-color-neutral-100) 25%, var(--ha-color-neutral-200) 50%, var(--ha-color-neutral-100) 75%); background-size: 200% 100%; animation: ha-shimmer 1.5s infinite;`
- Skeleton div: 3-4 fake card shapes (rounded rectangles) stacked vertically
- `@keyframes ha-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`
- At `prefers-reduced-motion: reduce`, use static `background-color: var(--ha-color-neutral-100)` without animation

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** #461
