---
type: story
id: miwk_JpwDtKy
title: "feat(ui): mobile-optimized pagination and filter bar"
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
epic_ref:
  id: STHgdkjlft50
github:
  issue_number: 464
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5419b6315eb673b6e2cb89206334e1ef883ec731254cffecf81cfe95ca33d964
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:45:14Z
updated_at: 2026-04-01T21:45:14Z
---

## Summary

Optimize pagination and filter bar components for mobile viewports. Pagination stacks vertically with centered controls. Filter bar uses full-width controls that stack vertically.

## Scenarios

**Scenario: pagination stacks vertically on mobile**
  Given viewport width is 375px
  When  the list view loads with multiple pages
  Then  the pagination info text and controls stack vertically
  And   controls are centered
  And   Previous/Next buttons have minimum 44px height

**Scenario: pagination info shows compact text on mobile**
  Given viewport width is 375px
  When  the list view loads with pagination
  Then  the "Showing X to Y of Z results" text wraps gracefully
  And   the "Page N of M" indicator is clearly visible

**Scenario: filter bar controls stack full-width on mobile**
  Given viewport width is 375px
  When  the filter bar is expanded
  Then  each filter select occupies full width
  And   filters stack vertically with consistent spacing

**Scenario: search input is full-width on mobile**
  Given viewport width is 375px
  When  the list view loads
  Then  the search input spans the full content width

## Acceptance criteria

- [ ] Pagination stacks vertically on mobile with centered controls
- [ ] Pagination info wraps gracefully
- [ ] Filter controls stack full-width on mobile
- [ ] Search input spans full width on mobile

## Files to modify

- `src/hyperadmin/static/css/_pagination.css`
- `src/hyperadmin/static/css/_filter.css`
- `src/hyperadmin/static/css/_search.css`
- `src/hyperadmin/static/css/_responsive.css`

## Implementation notes

- Pagination: `.ha-pagination { flex-direction: column; align-items: center; gap: var(--ha-space-3); }` at mobile
- Filter bar: `.ha-filter-container { flex-direction: column; }` and `.ha-filter-group { width: 100%; }` at mobile
- Pagination buttons should comply with 44px min-height from `_accessibility.css`

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** #461
