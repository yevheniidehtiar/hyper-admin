---
type: epic
id: M437OCoW6YMr
title: "epic(plugin-tasks): hyperadmin-tasks foundation — TaskBackend port, in-memory backend, contract suite"
status: in_progress
priority: high
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
  issue_number: 739
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Create the `hyperadmin-tasks` plugin package and its backend-agnostic `TaskBackend`
port (read models + capability flags), an `InMemoryTaskBackend`, and a reusable backend
contract test suite. This is the **seam epic**: the pgtask adapter and the UI epics both
build on it and can then proceed in parallel.

**SDD:** [`docs/specs/plugin-tasks.md`](../../../docs/specs/plugin-tasks.md) — first story is the human review gate.

## Tasks

- [ ] #744 reviewspec-approve-sdd-for-plugin-tasks
- [ ] #740 chore-scaffold-plugins-hyperadmin-tasks-package
- [ ] #743 feat-plugin-tasks-taskbackend-port-and-read-models
- [ ] #745 test-plugin-tasks-backend-contract-suite
- [ ] #741 feat-plugin-tasks-inmemory-backend
- [ ] #742 feat-plugin-tasks-settings-and-backend-wiring

## Scenarios

**Scenario: plugin is discovered and registers its seams**
  Given hyperadmin-tasks is installed in the workspace
  When  Admin is constructed with plugins enabled
  Then  the "tasks" plugin is registered with a /tasks page, a "Tasks" nav section and view_tasks / manage_tasks permissions

**Scenario: in-memory backend passes the contract suite**
  Given the backend contract suite
  When  it is run against InMemoryTaskBackend
  Then  every contract test passes

## Acceptance Criteria

- [ ] SDD approved (human gate)
- [ ] Plugin discovered via `hyperadmin.plugins` entry point, disable-able via `disabled_plugins=["tasks"]`
- [ ] `TaskBackend` port + read models + `Capability` published from `hyperadmin_tasks.backend`
- [ ] `InMemoryTaskBackend` passes the contract suite
- [ ] Zero changes to `src/hyperadmin/core/` (or a separately reviewed seam PR)
