---
type: story
id: RsQl66bUKdBJ
title: "review(spec): approve SDD for hyperadmin-tasks"
status: backlog
priority: high
assignee: null
labels:
  - size:S
  - planned
  - plugin
  - needs-human
  - plugin
estimate: null
epic_ref:
  id: M437OCoW6YMr
github:
  issue_number: 744
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-10-29T00:00:00Z
---

## Context

**Human gate** — review and approve `docs/specs/plugin-tasks.md` before any implementation story starts.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: SDD is approved**
  Given the SDD draft is committed
  When  the owner reviews it and resolves the Open Questions
  Then  Status is set to Approved and implementation stories are unblocked

## Acceptance Criteria

- [ ] Port shape (methods, read models, capabilities) accepted
- [ ] pgtask maturity risk (pre-alpha, unstable view columns) accepted with the adapter isolation strategy
- [ ] Open Questions resolved (async startup seam, admin SQL functions, audit, extras, polling vs SSE)

## Files Likely Affected

- `docs/specs/plugin-tasks.md`

## Dependencies

Depends on: none

## Notes for Implementer

Not an agent task — leave for the owner.
