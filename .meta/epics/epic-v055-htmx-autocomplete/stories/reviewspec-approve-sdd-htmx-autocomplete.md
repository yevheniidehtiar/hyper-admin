---
type: story
id: st-v055-ac-00
title: "review(spec): approve SDD for HTMX autocomplete"
status: done
priority: high
assignee: null
labels:
  - size:S
  - done
  - needs-human
  - upstream-readiness
  - H6
estimate: null
epic_ref:
  id: ep-v055-ac-01
created_at: 2026-05-10T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
closed_at: 2026-05-11T00:00:00Z
---

## Summary

**Human gate** — review and approve `docs/specs/htmx-autocomplete.md` before
implementation sub-tasks may start.

## Approval

**Approved by Yevhenii Dehtiar on 2026-05-11.** SDD status moved to `Approved`
in `docs/specs/htmx-autocomplete.md`. Implementation sub-tasks are now
unblocked.

## Checklist

- [x] Problem statement scoped to H6 only (no virtualised dropdown, no M2M chips)
- [x] Goals measurable against BDD scenarios
- [x] Non-goals defer pagination, cross-admin popups, custom widget plugin API
- [x] BDD scenarios cover happy + dependent + popup + display_template paths
- [x] `AdminOptions` change is backward compatible (new fields default to None)
- [x] Popup uses `HX-Trigger` event (not navigation)
- [x] `use_autocomplete_widget=True` default is safe (legacy admins opt out)
- [x] Open Questions resolved (see below)

## Open Questions resolved

1. **`relation_display` accepts `str | Callable[[Any], str]`.** Format
   strings remain the documented common path; callables are the escape hatch.
2. **Single `<div id="ha-popup-root">` slot** in `base.html`. HTMX swaps the
   modal contents in/out; close via `hx-on::after-request="this.innerHTML=''"`.
3. **Multi-parent `depends_on: list[str]` deferred.** v0.5.5 ships
   single-string `depends_on`; the field can widen later without breaking
   compatibility.

## Blocked by

(none — SDD draft is committed)

## Parent

- Epic: `epic-v055-htmx-autocomplete`
