---
type: epic
id: PWKqpZ5lCyfD
title: "epic(plugin-tasks): Flower-lite monitoring UI — dashboard, tasks, workers, schedules, actions"
status: backlog
priority: medium
owner: null
labels:
  - epic
  - agent-task
  - size:L
  - planned
  - plugin
milestone_ref:
  id: iOTodDwZehp2
github:
  issue_number: 752
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Overview

Admin-native monitoring UI on top of the `TaskBackend` port (server-rendered Jinja + HTMX,
polling refresh). Developed against `InMemoryTaskBackend`, so it runs **in parallel** with the
pgtask adapter epic. All assertable elements get `data-testid="tasks-<element>"`.

**SDD:** [`docs/specs/plugin-tasks.md`](../../../docs/specs/plugin-tasks.md)

## Tasks

- [ ] #754 feat-plugin-tasks-ui-dashboard
- [ ] #756 feat-plugin-tasks-ui-task-list
- [ ] #755 feat-plugin-tasks-ui-task-detail
- [ ] #757 feat-plugin-tasks-ui-workers-and-schedules
- [ ] #753 feat-plugin-tasks-ui-actions
- [ ] #758 test-e2e-plugin-tasks-monitoring-ui

## Scenarios

**Scenario: operator retries a failed task**
  Given a failed task on queue "reports" and a user with manage_tasks
  When  the user opens the task, clicks "Retry" and confirms
  Then  the task shows state "pending" and a success message is displayed

**Scenario: read-only user cannot act**
  Given a user with view_tasks but not manage_tasks
  When  the user opens a failed task
  Then  no Retry or Cancel buttons are rendered and POSTing the action returns 403

## Acceptance Criteria

- [ ] Dashboard, task list, task detail, workers and schedules pages
- [ ] Actions gated by `manage_tasks` + backend capabilities; CSRF-protected
- [ ] HTMX polling every `refresh_seconds` (0 disables)
- [ ] Playwright E2E suite per BDD conventions; visual baselines refreshed

## Blocked by

- epic-plugin-tasks-foundation (port + in-memory backend + settings)
