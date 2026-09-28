---
type: story
id: st-v058-byoa-00
title: "review(spec): approve BYOA SDD"
status: todo
priority: critical
assignee: null
labels:
  - size:S
  - planned
  - area:docs
  - layer:gate
  - needs-human
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

**Human gate.** Review and approve the Bring Your Own App design doc before any implementation story starts. Record the answers to the seven *Owner decisions needed* at the top of the SDD (or accept the recommended defaults), then set the SDD status to `Approved`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: Owner decisions needed; Open Questions

## Checklist

- [ ] Problem, goals and non-goals match the BYOA thesis (10-minute add to an existing app)
- [ ] Owner decisions 1-7 answered (or the recommended defaults accepted)
- [ ] Module boundaries comply with CONSTITUTION §1/§2 (pure core modules; views reach introspection via BaseAdapter)
- [ ] Breaking defaults (isolated mount, CSRF enforce, create_tables=False, filter whitelist) accepted with their escape hatches
- [ ] BDD scenarios cover the happy path and at least one failure path per pillar
- [ ] The story breakdown order and `Blocked by` graph are acceptable
- [ ] Decide whether `st-v058-byoa-10` (authz gaps) ships ahead as a standalone fix
- [ ] Set the SDD `Status` to `Approved`

## Files to Change

- `docs/specs/bring-your-own-app.md`

## Blocked by

- none

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
