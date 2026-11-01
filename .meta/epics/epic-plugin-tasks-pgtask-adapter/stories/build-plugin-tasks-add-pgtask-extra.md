---
type: story
id: CPPMKcI20Qt4
title: "build(plugin-tasks): add [pgtask] optional extra"
status: backlog
priority: high
assignee: null
labels:
  - agent-task
  - size:S
  - planned
  - plugin
estimate: null
epic_ref:
  id: krqQHG094vaz
github:
  issue_number: 747
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

Deps-lane PR: dependency changes ship alone (CONSTITUTION §7).

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: extra installs pgtask**
  Given a clean env
  When  `uv sync --extra pgtask` runs in plugins/hyperadmin-tasks
  Then  pgtask>=0.4,<0.5 and psycopg are importable

## Acceptance Criteria

- [ ] `[project.optional-dependencies].pgtask = ["pgtask>=0.4,<0.5", "psycopg>=3.2"]`
- [ ] Lock updated
- [ ] Matrix check per deps feedback (3.11/3.14 lowest-direct, 3.14 highest)

## Files Likely Affected

- `plugins/hyperadmin-tasks/pyproject.toml`
- `uv.lock`

## Dependencies

Depends on: `chore-scaffold-plugins-hyperadmin-tasks-package`

## Notes for Implementer

pgtask ships abi3 wheels for macOS/Linux/Windows; sdist needs Rust — verify CI uses wheels.
