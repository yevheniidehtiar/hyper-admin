---
type: story
id: st-v058-byoa-54
title: "chore(dogfood): dogfood-0 from a repository install once the bridge and isolated mount land"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:core
  - layer:gate
  - dogfood
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Before the whole plan is built, install HyperAdmin from the repository (`develop`) into a real, pre-existing FastAPI app, which is not named in this repo. Do it as soon as the isolated mount (`-35`) and the bridge with the token handoff and login form (`-41`) have landed.

Follow the draft guide notes, and time the run. File every friction point as a framework-neutral story before pillars D and E finish, so that blockers are found early rather than after the release.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: Rollout

## Scenarios

```
Scenario: dogfood-0 gap log is filed
  Given HyperAdmin installed from develop into an existing app with its own auth and UUID keys
  When  the maintainer mounts the admin following the draft notes
  Then  the time taken and every friction point are recorded
  And   each blocking gap is filed as a story in this epic
```

## Acceptance Criteria

- [ ] Gap log recorded, with the elapsed time
- [ ] Blocking gaps filed as stories and linked from the epic
- [ ] No downstream project names are written into the repository

## Blocked by

- `featcore-isolated-sub-application-mount` (st-v058-byoa-35)
- `featauth-token-handoff-post-auth-session-and-bridge-logout` (st-v058-byoa-41)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
