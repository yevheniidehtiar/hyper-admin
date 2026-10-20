---
type: story
id: st-v056-dp-00
title: "review(spec): approve SDD for detail panels"
status: done
priority: high
assignee: null
labels:
  - size:S
  - done
  - needs-human
  - upstream-readiness
  - H4
estimate: null
epic_ref:
  id: ep-v056-dp-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-10-20T00:00:00Z
closed_at: 2026-10-20T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/detail-panels.md` before
implementation sub-tasks may start.

## Approval

**Approved by Yevhenii Dehtiar on 2026-10-20.** SDD status moved to `Approved`
in `docs/specs/detail-panels.md`. Implementation sub-tasks are now unblocked.

## Checklist

- [x] H4 scope (registry + tabbed layout + PDF demo) — confirmed correct
- [x] History/Transitions panel content excluded — confirmed correct
- [x] BDD scenarios cover happy + streaming + forbidden + collision paths
- [x] Backward compatible (no `panels` → renders unchanged `detail.html`)
- [x] Default permission codename scheme acceptable
- [x] Open Questions resolved (see below)

## Open Questions resolved

1. **Panel handlers receive the loaded instance** — `handler(self, request, obj)`.
   The view loads `obj` once; panels never re-fetch.
2. **New `hyperadmin.panels` package**, re-exported from `hyperadmin.__init__`;
   `pdf_stream_panel` lives there.
3. **`PanelDef.enabled: Callable[[Any], bool] | None` is added** for
   instance-scoped tab visibility.

## Parent

- Epic: `epic-v056-detail-panels`
