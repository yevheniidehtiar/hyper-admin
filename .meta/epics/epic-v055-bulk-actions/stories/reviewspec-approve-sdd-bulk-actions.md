---
type: story
id: st-v055-bulk-00
title: "review(spec): approve SDD for bulk actions"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/bulk-actions.md` before
implementation sub-tasks may start.

## Checklist

- [ ] Problem statement scoped to H3 only (no creep into queues / async)
- [ ] Goals measurable against BDD scenarios
- [ ] Non-goals defer async execution, cross-model bulk, streaming progress
- [ ] BDD scenarios cover happy path + ≥1 failure path + permission failure
- [ ] `ActionDef` change is backward compatible (new fields default to False/None)
- [ ] Endpoint naming `/actions/{name}/bulk` vs `/{id}/action/{name}` decided
- [ ] Object-permission re-check policy confirmed
- [ ] Open Questions resolved (auto-require-selection default, select-all-matching, rollback)

## Open Questions to resolve

1. Should `bulk=True` imply `requires_selection=True` by default?
2. Accept `select_all_matching_filter=true` in v0.5.5 or defer?
3. Expose a "rollback" affordance on the result page, or rely on audit log?

## Blocked by

(none — SDD draft is committed)

## Parent

- Epic: `epic-v055-bulk-actions`
