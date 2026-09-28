---
type: story
id: st-v058-byoa-43
title: "fix(views): list_view logs and surfaces DB errors instead of swallowing them"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:views
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Catch only `SQLAlchemyError` and call `logger.exception`. Re-raise in debug mode. Otherwise render a `list-error` banner (500 for a full page, 200 for HTMX), adding a migration hint when a table is missing.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.2

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/templates/list_layout.html`
- `tests/unit/test_list_view_errors.py`

## Scenarios

```
Scenario: DB error surfaced
  Given the model table is missing
  When  the list is opened
  Then  the list-error banner mentions migrations
  And   an ERROR log with a traceback is emitted

Scenario: debug re-raises
  Given settings.debug=True and a failing query
  When  the list is opened
  Then  the exception propagates
```

## Acceptance Criteria

- [ ] DB error surfaced
- [ ] debug re-raises
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactorviews-dynamicmodelview-item-handlers-use-self-pk-and` (st-v058-byoa-29)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
