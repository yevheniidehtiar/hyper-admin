---
type: story
id: st-v056-dp-00
title: "review(spec): approve SDD for detail panels"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H4
estimate: null
epic_ref:
  id: ep-v056-dp-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/detail-panels.md` before
implementation sub-tasks may start.

## Checklist

- [ ] H4 scope (registry + tabbed layout + PDF demo) — confirmed correct
- [ ] History/Transitions panel content excluded — confirmed correct
- [ ] BDD scenarios cover happy + streaming + forbidden + collision paths
- [ ] Backward compatible (no `panels` → renders unchanged `detail.html`)
- [ ] Default permission codename scheme acceptable
- [ ] Open Questions resolved (handler signature, package naming, `enabled` predicate)

## Open Questions to resolve

1. Pass `obj` to panel handlers or only `request, item_id`?
2. `hyperadmin.panels` package vs `hyperadmin.panels.streams`?
3. Add `PanelDef.enabled: Callable[[Any], bool] | None` for instance-scoped visibility?

## Parent

- Epic: `epic-v056-detail-panels`
