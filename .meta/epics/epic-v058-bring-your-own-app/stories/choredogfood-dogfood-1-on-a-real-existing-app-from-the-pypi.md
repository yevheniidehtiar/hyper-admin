---
type: story
id: st-v058-byoa-52
title: "chore(dogfood): dogfood-1 on a real existing app from the PyPI alpha; gap log"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:dogfood
  - layer:gate
  - needs-human
  - dogfood
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Install `hyper-admin==0.5.0a1` from PyPI into a real, pre-existing application (never named in this repo), following only the guide and timing it. File every friction point as a framework-neutral story. Blockers are fixed in v0.5.8 and released as the next alpha. This supersedes re-cut stub `st-v058-byoa-07`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: Rollout

## Files to Change

- `.meta/epics/epic-v058-bring-your-own-app/stories/`

## Scenarios

```
Scenario: 10-minute setup
  Given a clean checkout of an existing FastAPI app
  When  the guide is followed start to finish
  Then  the admin works in 10 minutes or less

Scenario: gaps are filed
  Given a friction point is found
  When  the gap log is reviewed
  Then  a framework-neutral story exists for it
```

## Acceptance Criteria

- [ ] 10-minute setup
- [ ] gaps are filed
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `buildrelease-0-5-0a1-pep440-commitizen-version-and-fixed-rel` (st-v058-byoa-50)
- `docsguides-existing-app-guide-examples-byoa-csrf-upgrade-not` (st-v058-byoa-51)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
