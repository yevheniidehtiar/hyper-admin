---
type: story
id: st-perf-02
title: "review(spec): approve ASGI middleware SDD"
status: done
priority: high
assignee: null
labels:
  - size:S
  - area:docs
  - layer:gate
  - needs-human
estimate: null
epic_ref:
  id: fkINeqAy7AVG
created_at: 2026-11-07T00:00:00Z
updated_at: 2026-11-07T00:00:00Z
---

## Summary

**Human gate.** Review the SDD for converting the four `BaseHTTPMiddleware` classes to plain ASGI, then set its status to `Approved`.

**Spec:** [`docs/specs/asgi-middleware.md`](../../../../docs/specs/asgi-middleware.md)

## Files to Change

- docs/specs/asgi-middleware.md

## Acceptance Criteria

- [ ] Goals and non-goals accepted
- [ ] Behaviour-preserving scope confirmed (no public API change)
- [ ] SDD `Status` set to `Approved`

## Blocked by

- none

## Parent

- Epic: `epic-adapter-query-performance-selectinload-pagination-count`
