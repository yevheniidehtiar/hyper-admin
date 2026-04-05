---
type: story
id: A9Gd8d91JwQM
title: "docs(spec): SDD for Pydantic Settings — HyperAdminSettings"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:docs
  - size:S
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 374
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:03f60f8aa22d419a092c479c09b97a82ea113b30ee44712917a67eca9c37f7b8
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T09:01:37Z
updated_at: 2026-03-31T09:29:34Z
---

## Context

Human gate: approve the design for Pydantic Settings before implementation begins. This epic touches `core/`, `db.py`, and potentially `views/` — SDD is required per convention.

## Acceptance criteria

- [x] SDD created as GitHub issue or document with: Problem, Goals, Non-Goals, BDD Scenarios, Design, Edge Cases, Migration
- [ ] Human reviewer approves the design
- [x] Open questions resolved before implementation starts

## Key Design Questions

1. Should `HyperAdminSettings` be a required param on `Admin()` or optional with auto-instantiation?
2. What is the priority order: explicit `Admin()` params > settings object > env vars > defaults?
3. Should `database_url` be part of settings or remain a separate `engine` param?
4. Should settings be accessible from Jinja2 templates?
5. `env_prefix`: `HYPERADMIN_` or `HA_`?

## Dependencies

None — this blocks all C1-C6 implementation tasks.
