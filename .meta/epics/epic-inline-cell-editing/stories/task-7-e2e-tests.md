---
type: story
id: ice-task-7
title: "Task 7: E2E tests — one Playwright test per BDD scenario"
status: done
priority: medium
labels:
  - test
  - e2e
estimate: 5
epic_ref:
  id: epic-inline-cell-editing
created_at: 2026-05-03
updated_at: 2026-05-03
---

## Description

Add `tests/e2e/test_inline_cell_editing.py`. One Playwright test per BDD
scenario from the SDD. Each test must include inline `# Given / # When /
# Then` comments and use accessibility-first locators
(`get_by_role`, `get_by_label`, `get_by_test_id`).

The example app must declare `list_editable` on at least one ModelAdmin
(reuse `User` with `list_editable = ["name", "is_active"]`).

## Acceptance Criteria

- [ ] One test per BDD scenario in the SDD
- [ ] Tests use `data-testid` per the project convention (no `.ha-*` selectors)
- [ ] Tests pass under `poe test:e2e -k inline_cell`
