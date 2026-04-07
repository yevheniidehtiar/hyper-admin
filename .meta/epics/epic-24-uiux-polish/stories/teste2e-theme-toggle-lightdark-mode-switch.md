---
type: story
id: O_oZ2KBLxs-v
title: "test(e2e): theme toggle light/dark mode switch"
status: done
priority: medium
assignee: null
labels:
  - task
  - design
  - themes
estimate: null
epic_ref:
  id: MypYvtdOO7hk
github:
  issue_number: 335
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:19478536b88144da82923f283d2314286574f3daedffd589b0f4da7c10a0a751
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T09:36:35Z
updated_at: 2026-03-29T10:37:31Z
---

## Description

Add Playwright E2E tests covering the theme toggle feature (#73, PR #300).

## Test Scenarios

- [ ] Theme toggle button is visible in the navbar
- [ ] Clicking toggle switches body class to dark theme
- [ ] Clicking toggle again reverts to light mode
- [ ] Theme preference persists across page navigation (localStorage)
- [ ] Dark mode applies correct background/text colors
- [ ] Sun/moon icons toggle visibility correctly

## Acceptance Criteria

- All scenarios pass in Playwright Chromium
- Uses accessibility-first selectors (`get_by_role`, `get_by_label`, `get_by_test_id`)
- No `.ha-*` CSS class selectors in tests

## Context

Blocked until PR #300 is merged (theme toggle implementation).
