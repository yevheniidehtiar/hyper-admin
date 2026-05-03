---
type: story
id: J8f2apydnSaO
title: "test(e2e): responsive design viewport and interaction tests"
status: done
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - responsive
  - e2e
  - cycle:3
estimate: null
epic_ref:
  id: RspSynth_01
github:
  issue_number: 471
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e1c3d0b6be23ac5b8a85e7079c6707cc37dd9514b4264c0aadbce3f67da43b63
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:46:03Z
updated_at: 2026-04-01T21:46:19Z
---

## Summary

Comprehensive E2E tests for all responsive behaviors using Playwright viewport emulation. Tests verify sidebar toggle, table card layout, pagination stacking, form touch targets, page header stacking, and navbar behavior across mobile (375x667), tablet (768x1024), and desktop (1280x720) viewports.

Downsized from L to M by focusing on core viewport tests. Visual regression screenshots are in a separate story (C3-D).

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

**Scenario: form grid is single column on mobile**
  Given viewport is 375x667 and a create form loads
  When  inspecting the form layout
  Then  form fields are in a single column

**Scenario: page header stacks on mobile**
  Given viewport is 375x667 and the list view loads
  When  inspecting the page header
  Then  the heading and "Create New" button are stacked vertically

**Scenario: login page is usable on mobile**
  Given viewport is 375x667
  When  the login page loads
  Then  the login card is centered and inputs are full-width

**Scenario: inputs do not trigger zoom on iOS mobile**
  Given viewport is 375x667 and a create form loads
  When  inspecting input element styles
  Then  all input elements have computed font-size >= 16px

**Scenario: Escape key closes mobile sidebar**
  Given viewport is 375x667 and the sidebar is open
  When  the user presses the Escape key
  Then  the sidebar closes

## Acceptance criteria

- [ ] Hamburger opens/closes sidebar on mobile
- [ ] Sidebar inline on desktop
- [ ] Table stacked cards on mobile, horizontal on desktop
- [ ] Pagination stacked on mobile
- [ ] Form grid single column on mobile
- [ ] Page header stacks on mobile
- [ ] Login page usable on mobile
- [ ] Inputs have 16px+ font-size on mobile (no iOS zoom)
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

- **Size:** M
- **Tier:** Opus
- **blocked_by:** all Cycle 2 stories
