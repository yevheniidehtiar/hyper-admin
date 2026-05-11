---
type: story
id: st-v055-bulk-00
title: "review(spec): approve SDD for bulk actions"
status: done
priority: high
assignee: null
labels:
  - size:S
  - done
  - needs-human
  - upstream-readiness
  - H3
estimate: null
epic_ref:
  id: ep-v055-bulk-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
closed_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/bulk-actions.md` before
implementation sub-tasks may start.

## Approval

**Approved by Yevhenii Dehtiar on 2026-05-11.** SDD status moved to `Approved`
in `docs/specs/bulk-actions.md`. Implementation sub-tasks are now unblocked.

## Checklist

- [x] Problem statement scoped to H3 only (no creep into queues / async)
- [x] Goals measurable against BDD scenarios
- [x] Non-goals defer async execution, cross-model bulk, streaming progress
- [x] BDD scenarios cover happy path + ≥1 failure path + permission failure
- [x] `ActionDef` change is backward compatible (new fields default to False/None)
- [x] Endpoint naming `/actions/{name}/bulk` (decided)
- [x] Object-permission re-check policy confirmed (re-checked per row)
- [x] Open Questions resolved (see below)

## Open Questions resolved

1. **`bulk=True` implies `requires_selection=True` by default.** Explicit
   `requires_selection=False` opt-out remains supported for "operate on all
   matching rows" actions.
2. **`select_all_matching_filter` deferred** beyond v0.5.5. Explicit-ids only
   for now; reopened as a discrete story if a downstream demo needs it.
3. **No "rollback" affordance** on the result page. The audit log (v0.5.1) is
   the rollback surface; the result page will link to the audit entries for
   each failed row.

## Blocked by

(none — SDD draft is committed)

## Parent

- Epic: `epic-v055-bulk-actions`
