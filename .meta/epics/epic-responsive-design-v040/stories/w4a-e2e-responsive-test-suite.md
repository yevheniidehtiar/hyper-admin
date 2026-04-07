---
type: story
id: B57RGgp05uU0
title: "test(e2e): responsive viewport tests for all admin views"
status: todo
priority: medium
assignee: null
labels:
  - frontend
  - testing
  - size:M
  - responsive
  - cycle:3
estimate: null
epic_ref:
  id: cvr4sYoEN9CV
github:
  issue_number: null
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: null
  synced_at: null
created_at: 2026-04-07T00:00:00Z
updated_at: 2026-04-07T00:00:00Z
---

## Summary

Create a Playwright E2E test suite that validates responsive behavior at mobile (375px),
tablet (768px), and desktop (1024px) viewports for all major admin views: list, create,
update, detail, login, dashboard.

## Scenarios

**Scenario: list view renders stacked cards at mobile viewport**
  Given viewport width is 375px
  When  the list view loads with data
  Then  table rows render as stacked cards

**Scenario: sidebar is hidden on mobile and visible on desktop**
  Given viewport width is 375px
  When  any admin page loads
  Then  the sidebar is not visible
  And   the hamburger button is visible

**Scenario: hamburger toggles sidebar on mobile**
  Given viewport width is 375px and the admin page is loaded
  When  the user clicks the hamburger button
  Then  the sidebar becomes visible as an overlay

**Scenario: forms are single-column on mobile**
  Given viewport width is 375px
  When  a create form loads
  Then  form fields display in a single column

**Scenario: desktop layout unchanged**
  Given viewport width is 1024px
  When  the list view loads
  Then  sidebar is visible inline and table displays as horizontal rows

## Acceptance criteria

- [ ] Tests cover mobile, tablet, desktop for list, create, detail, login
- [ ] Sidebar visibility tests at mobile and desktop
- [ ] Hamburger toggle test
- [ ] Form single-column test on mobile
- [ ] Desktop regression test

## Files to modify

- `tests/e2e/test_responsive.py` — new test file

## Demo checkpoint

Run `poe test:e2e -- tests/e2e/test_responsive.py` — all tests pass.

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** all Cycle 2 stories (C2-A, C2-B, C2-C, C2-D)
