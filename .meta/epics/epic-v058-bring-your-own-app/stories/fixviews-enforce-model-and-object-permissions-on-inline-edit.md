---
type: story
id: st-v058-byoa-10
title: "fix(views): enforce model and object permissions on inline edit/save, update form, file delete and single actions"
status: todo
priority: critical
assignee: null
labels:
  - size:S
  - planned
  - area:views
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Close live authorization gaps. `inline_edit_form_view` and `inline_save_view` skip `_check_permission` and `_check_object_permission`. `update_form_view` and `delete_file_view` skip the object check. `run_action` never loads the object, never applies `_request_queryset_filter` and never checks `action_<name>`. This is security-relevant today, so it can ship ahead of the SDD (Owner decision 4).

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B.6

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `tests/unit/test_dynamic_authz_gaps.py`

## Scenarios

```
Scenario: inline cell save enforces change permission
  Given the user lacks change_order
  When  POST /admin/order/5/inline/status is sent
  Then  the response is 403
  And   the field is unchanged

Scenario: inline edit form enforces object permission
  Given an object permission checker denies change on order 5
  When  GET /admin/order/5/inline/status/edit is requested
  Then  the response is 403

Scenario: single action enforces object permission
  Given an object permission checker denies action_archive on order 5
  When  the archive action is run on order 5
  Then  the response is 403
  And   the action handler is not called

Scenario: single action respects the queryset filter
  Given get_queryset hides order 5 from the user
  When  the archive action is run on order 5
  Then  the response is 404
```

## Acceptance Criteria

- [ ] inline cell save enforces change permission
- [ ] inline edit form enforces object permission
- [ ] single action enforces object permission
- [ ] single action respects the queryset filter
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)
- *(may be unblocked early — Owner decision 4 in the SDD)*

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
