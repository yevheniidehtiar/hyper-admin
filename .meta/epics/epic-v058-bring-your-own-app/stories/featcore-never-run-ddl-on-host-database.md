---
type: story
id: st-v058-byoa-03
title: "feat(core): never run DDL on the host database"
status: todo
priority: critical
assignee: null
labels:
  - planned
  - area:core
  - size:S
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

`Admin` must not call `metadata.create_all` against a host engine by default. Make table creation an explicit opt-in (e.g. `create_tables=True` for demos/examples) and document that migrations stay with the host app.

## Acceptance Criteria

- [ ] Default `Admin(...)` issues no DDL (asserted in tests)
- [ ] Examples opt in explicitly
- [ ] Changelog notes the behaviour change

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
