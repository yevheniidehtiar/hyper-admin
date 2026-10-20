---
type: story
id: st-v057-pmx-00
title: "review(spec): approve SDD for permission-matrix UI"
status: done
priority: high
assignee: null
labels:
  - size:S
  - done
  - needs-human
  - upstream-readiness
  - H20
estimate: null
epic_ref:
  id: ep-v057-pmx-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-20T00:00:00Z
closed_at: 2026-10-20T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/permission-matrix-ui.md`
before implementation sub-tasks may start.

## Approval

**Approved by Yevhenii Dehtiar on 2026-10-20.** SDD status moved to `Approved`
in `docs/specs/permission-matrix-ui.md`. Implementation sub-tasks are now unblocked.

## Checklist

- [x] H20 scope (model × action grid + object column + bulk save + audit)
- [x] Standalone view module (not a `ModelAdmin`), registered through the plugin registry — boundary acceptable
- [x] `Group.permissions_version` schema addition acceptable
- [x] Optimistic concurrency strategy (per-group version) acceptable
- [x] Object permission popover (not modal / drawer) — confirmed
- [x] Bundling `examples/full-demo/` here — confirmed
- [x] Open Questions resolved (see below)

## Open Questions resolved

1. **Groups only.** Roles are a future epic (v0.5.8 was bring-your-own-app,
   not roles); H20 acceptance only needs groups.
2. **Rely on the existing CSRF guard** shipped in v0.5.8 (`HyperAdminRoute`,
   signed double-submit cookie + `X-CSRF-Token` header); no per-save token.
3. **Per-column "select all" toggle: yes.**

## Parent

- Epic: `epic-v057-permissions-matrix`
