---
type: story
id: Efx_RpqPnhlF
title: 'docs(plugin-tasks): plugin docs page, role setup and "Coming from Celery" guide'
status: backlog
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - documentation
  - planned
  - plugin
estimate: null
epic_ref:
  id: UuoF0wG2oyTQ
github:
  issue_number: 761
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

User-facing docs on the Zensical site.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: docs build**
  Given the new pages
  When  `poe docs:build` runs
  Then  the build succeeds and the page is in nav

## Acceptance Criteria

- [ ] Install + settings reference
- [ ] `pgtask configure-grants` observer/administrator role setup
- [ ] Celery mapping table incl. gaps (no canvas, no rate limits, Postgres-only)
- [ ] Prominent experimental / pre-alpha warning and version pin

## Files Likely Affected

- `docs/plugins/tasks.md`
- `zensical.toml`

## Dependencies

Depends on: `docs-plugin-tasks-example-app`

## Notes for Implementer

Follow CONSTITUTION.md; 100% patch coverage (`poe test:cov-diff`).
