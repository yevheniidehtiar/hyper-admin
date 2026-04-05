---
type: story
id: lhXc_tJbOByk
title: "test(e2e): responsive design viewport and interaction tests"
status: todo
priority: medium
assignee: null
labels:
  - size:L
  - planned
  - responsive
  - e2e
estimate: null
epic_ref: null
github:
  issue_number: 471
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e1c3d0b6be23ac5b8a85e7079c6707cc37dd9514b4264c0aadbce3f67da43b63
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:46:03Z
updated_at: 2026-04-01T21:46:19Z
---

## Summary

Comprehensive E2E tests for all responsive behaviors using Playwright viewport emulation. Tests verify sidebar toggle, table card layout, pagination stacking, form touch targets, and navbar behavior across mobile (375x667), tablet (768x1024), and desktop (1280x720) viewports.

## Scenarios

**Scenario: hamburger button opens and closes sidebar on mobile**
  Given viewport is 375x667 and the admin page is loaded
  When  the user clicks the hamburger button
  Then  the sidebar overlay slides in
  And   clicking the backdrop closes it

**Scenario: sidebar is inline on desktop viewport**
  Given viewport is 1280x720 and the admin page is loaded
  When  the page loads
  Then  the sidebar is visible inline
  And   no hamburger button is visible

**Scenario: table renders as stacked cards on mobile**
  Given viewport is 375x667 and a list view loads with rows
  When  inspecting the table
  Then  each row renders as a card with label-value pairs

**Scenario: table renders as horizontal table on desktop**
  Given viewport is 1280x720 and a list view loads with rows
  When  inspecting the table
  Then  the table renders with visible header row and horizontal rows

**Scenario: pagination stacks vertically on mobile**
  Given viewport is 375x667 and a list view loads with pagination
  When  inspecting the pagination
  Then  info text and controls are stacked vertically

**Scenario: filter controls are full-width on mobile**
  Given viewport is 375x667 and filters are expanded
  When  inspecting the filter bar
  Then  each filter select occupies full width

**Scenario: form grid is single column on mobile**
  Given viewport is 375x667 and a create form loads
  When  inspecting the form layout
  Then  form fields are in a single column

**Scenario: Escape key closes mobile sidebar**
  Given viewport is 375x667 and the sidebar is open
  When  the user presses the Escape key
  Then  the sidebar closes

## Acceptance criteria

- [ ] Hamburger opens/closes sidebar on mobile
- [ ] Sidebar inline on desktop
- [ ] Table stacked cards on mobile, horizontal on desktop
- [ ] Pagination stacked on mobile
- [ ] Filter controls full-width on mobile
- [ ] Form grid single column on mobile
- [ ] Escape closes sidebar

## Files to create

- `tests/e2e/test_responsive_design.py`

## Implementation notes

- Use `page.set_viewport_size()` for viewport emulation
- Follow accessibility-first selectors: `get_by_role`, `get_by_test_id`, `get_by_label`
- Inline `# Given / # When / # Then` comments per BDD convention
- Use `data-testid="sidebar-toggle"` for hamburger button
- Use `data-testid="sidebar"` for sidebar visibility checks

## Agent

- **Size:** L
- **Tier:** Opus
- **blocked_by:** #458, #461, #464, #465, #467, #470
