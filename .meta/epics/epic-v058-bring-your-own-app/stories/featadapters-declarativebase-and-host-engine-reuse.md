---
type: story
id: st-v058-byoa-04
title: "feat(adapters): plain SQLAlchemy 2.0 DeclarativeBase models + host engine reuse"
status: todo
priority: high
assignee: null
labels:
  - planned
  - area:adapters
  - size:M
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Register plain SQLAlchemy 2.0 `DeclarativeBase` models (not only SQLModel) with auto-discovery and smart defaults, and accept the host app's `AsyncEngine` / `async_sessionmaker` instead of creating a second pool.

## Acceptance Criteria

- [ ] DeclarativeBase models auto-discovered and fully CRUD-able
- [ ] `Admin(app, engine=host_engine)` / sessionmaker reuse documented and tested

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
