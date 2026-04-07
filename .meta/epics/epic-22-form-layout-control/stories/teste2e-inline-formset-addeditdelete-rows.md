---
type: story
id: nHOHfvdIK9k1
title: "test(e2e): inline formset add/edit/delete rows"
status: done
priority: medium
assignee: null
labels:
  - task
  - forms
  - inline-models
estimate: null
epic_ref:
  id: w5uOHybW-qhx
github:
  issue_number: 334
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:360b26ef66e40409a277e6f6e7889a26b65f8c79abf4f45f9990650848fda648
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T09:36:32Z
updated_at: 2026-03-30T15:38:25Z
---

## Description

Add Playwright E2E tests covering the inline formset feature (#68, PR #299).

## Test Scenarios

- [ ] Create view renders inline formset section with correct headings
- [ ] "Add row" button appends a new inline row via HTMX
- [ ] Filling inline fields and submitting the parent form persists inline rows
- [ ] Edit view pre-populates existing inline rows
- [ ] Delete checkbox marks an inline row for removal on save
- [ ] Validation errors on inline fields display correctly
- [ ] Empty extra rows are ignored on save

## Acceptance Criteria

- All scenarios pass in Playwright Chromium
- Uses accessibility-first selectors (`get_by_role`, `get_by_label`, `get_by_test_id`)
- No `.ha-*` CSS class selectors in tests

## Context

Blocked until PR #299 is merged (inline models implementation).
