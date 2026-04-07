---
type: story
id: Rsp4_e2e__06
title: "test(e2e): responsive design E2E test suite"
status: todo
priority: medium
assignee: null
labels:
  - testing
  - e2e
  - size:L
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

Create a comprehensive Playwright E2E test suite that validates all responsive design scenarios across mobile (375px), tablet (768px), and desktop (1024px) viewports. Tests run against the simple example app and cover every BDD scenario from the responsive epic.

## Scenarios

**Scenario: sidebar is hidden on mobile and shown on desktop**
  Given the Playwright browser viewport is 375px wide
  When  the admin dashboard loads
  Then  the sidebar is not visible
  And   the hamburger button is visible

**Scenario: hamburger opens sidebar overlay on mobile**
  Given the Playwright browser viewport is 375px wide and the page is loaded
  When  the hamburger button is clicked
  Then  the sidebar overlay slides in
  And   focus moves to the first sidebar link

**Scenario: data table shows card layout on mobile**
  Given the Playwright browser viewport is 375px wide
  When  the list view loads with data
  Then  each row is rendered as a vertical card
  And   data-label attributes are visible as inline labels

**Scenario: pagination stacks on mobile**
  Given the Playwright browser viewport is 375px wide
  When  the list view loads with pagination
  Then  the pagination controls are stacked vertically

**Scenario: forms are single-column on mobile**
  Given the Playwright browser viewport is 375px wide
  When  a create form loads
  Then  all form fields are displayed in a single column

**Scenario: login page is usable on mobile**
  Given the Playwright browser viewport is 375px wide
  When  the login page loads
  Then  the login card is centered and inputs are full-width

**Scenario: layout is correct at tablet breakpoint**
  Given the Playwright browser viewport is 768px wide
  When  the admin dashboard loads
  Then  the sidebar is visible inline with reduced width
  And   the layout is two-column

**Scenario: layout matches desktop design at 1024px**
  Given the Playwright browser viewport is 1024px wide
  When  the admin dashboard loads
  Then  the sidebar is at full width
  And   the hamburger button is not visible

**Scenario: page header stacks on mobile**
  Given the Playwright browser viewport is 375px wide
  When  the list view loads
  Then  the page heading and Create New button are stacked vertically

**Scenario: touch feedback is visible on mobile button tap**
  Given the Playwright browser viewport is 375px wide
  When  a button receives a pointer-down event
  Then  the button shows a visible active state

**Scenario: inputs do not trigger zoom on iOS mobile**
  Given the Playwright browser viewport is 375px wide
  When  a create form loads
  Then  all input elements have computed font-size >= 16px

## Acceptance criteria

- [ ] Mobile viewport tests: sidebar hidden, hamburger visible, card layout, stacked pagination
- [ ] Mobile form tests: single column, 16px font-size inputs, no iOS zoom
- [ ] Mobile login test: centered card, full-width inputs
- [ ] Mobile page header test: heading and actions stacked
- [ ] Mobile touch feedback test: buttons show active state
- [ ] Tablet test: two-column layout with narrow sidebar
- [ ] Desktop test: full sidebar, no hamburger, standard table

## Files to create

- `tests/e2e/test_responsive.py` -- Playwright test file with viewport fixtures

## Implementation notes

- Use Playwright `page.set_viewport_size({"width": 375, "height": 812})` for mobile
- Use accessibility-first locators per CLAUDE.md E2E selector convention
- `get_by_test_id("sidebar-toggle")` for hamburger
- `get_by_test_id("sidebar")` for sidebar
- `get_by_test_id("list-table")` for table
- Each test function named after its scenario title

## Agent

- **Size:** L
- **Tier:** Sonnet
- **blocked_by:** all responsive feat stories
