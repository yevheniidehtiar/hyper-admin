---
type: story
id: nxyIcMOgb2iK
title: "test(e2e): Playwright suite for the tasks monitoring UI"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - size:M
  - planned
  - plugin
estimate: null
epic_ref:
  id: PWKqpZ5lCyfD
github:
  issue_number: 758
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

E2E coverage mapped 1:1 to the UI scenarios (BDD conventions).

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: operator retries a failed task**
  Given the e2e app with a seeded InMemoryTaskBackend
  When  the operator retries a failed task
  Then  the detail shows pending and a success message

## Acceptance Criteria

- [ ] One test per UI scenario, named after the scenario, with # Given/# When/# Then comments
- [ ] Locators: get_by_role > get_by_label > get_by_text > get_by_test_id; no `.ha-*`
- [ ] Visual baselines refreshed in the same PR

## Files Likely Affected

- `tests/e2e/plugins/test_tasks_ui.py`

## Dependencies

Depends on: `feat-plugin-tasks-ui-actions`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
