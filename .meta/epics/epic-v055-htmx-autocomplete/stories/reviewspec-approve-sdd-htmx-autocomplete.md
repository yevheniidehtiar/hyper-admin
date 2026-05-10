---
type: story
id: st-v055-ac-00
title: "review(spec): approve SDD for HTMX autocomplete"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - needs-human
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-10T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/htmx-autocomplete.md` before
implementation sub-tasks may start.

## Checklist

- [ ] Problem statement scoped to H6 only (no virtualised dropdown, no M2M chips)
- [ ] Goals measurable against BDD scenarios
- [ ] Non-goals defer pagination, cross-admin popups, custom widget plugin API
- [ ] BDD scenarios cover happy + dependent + popup + display_template paths
- [ ] `AdminOptions` change is backward compatible (new fields default to None)
- [ ] Popup uses `HX-Trigger` event (not navigation) — confirmed correct
- [ ] `use_autocomplete_widget=True` default is safe (legacy admins opt out)
- [ ] Open Questions resolved (callable display, popup root location, multi-parent)

## Open Questions to resolve

1. Accept `Callable[[Any], str]` in addition to format strings for `relation_display`?
2. Single `<div id="ha-popup-root">` or per-widget popup containers?
3. Defer multi-parent `depends_on: list[str]` or design it in now?

## Blocked by

(none — SDD draft is committed)

## Parent

- Epic: `epic-v055-htmx-autocomplete`
