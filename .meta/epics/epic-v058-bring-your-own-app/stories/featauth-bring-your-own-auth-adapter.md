---
type: story
id: st-v058-byoa-05
title: "feat(auth): bring-your-own-auth adapter"
status: todo
priority: high
assignee: null
labels:
  - planned
  - area:auth
  - size:M
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Protocol that maps the host app's existing authentication (dependency, session, or user model) to admin identity and permissions, so HyperAdmin's built-in `User`/`Group` models become optional.

## Acceptance Criteria

- [ ] Host FastAPI dependency can authenticate admin requests
- [ ] Permission checks route through a host-provided callable
- [ ] Built-in auth remains the zero-config default

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
