---
type: story
id: st-v057-pmx-00
title: "review(spec): approve SDD for permission-matrix UI"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H20
estimate: null
epic_ref:
  id: ep-v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/permission-matrix-ui.md`
before implementation sub-tasks may start.

## Checklist

- [ ] H20 scope (model × action grid + object column + bulk save + audit)
- [ ] Standalone view module (not a `ModelAdmin`) — boundary acceptable
- [ ] `Group.permissions_version` schema addition acceptable
- [ ] Optimistic concurrency strategy (per-group version) acceptable
- [ ] Object permission popover (not modal / drawer) — confirmed
- [ ] Bundling `examples/full-demo/` here — confirmed (or move to a separate epic?)
- [ ] Open Questions resolved (groups-only vs roles, CSRF, select-all)

## Open Questions to resolve

1. Ship roles in v0.5.7 or groups-only?
2. CSRF: rely on global middleware or per-save token?
3. Add per-column "select all" toggle?

## Parent

- Epic: `epic-v057-permissions-matrix`
