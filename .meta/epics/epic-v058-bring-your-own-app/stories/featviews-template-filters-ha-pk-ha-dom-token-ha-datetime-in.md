---
type: story
id: st-v058-byoa-33
title: "feat(views): template filters ha_pk/ha_dom_token/ha_datetime_input/ha_display and timezone plumbing"
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

Add `views/template_filters.py` and register it in `HyperAdminRouter`. Pass `timezone` from `Admin` through the router to the view. `resolve_tz` reads `request.state.hyperadmin_timezone` first, then `settings.timezone`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: A.9

## Files to Change

- `src/hyperadmin/views/template_filters.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_template_filters.py`

## Scenarios

```
Scenario: ha_pk on dict and instance
  Given a row dict with _pk and a model instance
  When  ha_pk runs
  Then  the pk is returned for both

Scenario: ha_dom_token
  Given values 'a b?c' and 7
  When  ha_dom_token runs
  Then  a stable 'h…' token and '7' are returned

Scenario: per-request tz
  Given request.state.hyperadmin_timezone=Asia/Tokyo
  When  ha_display(aware dt) runs
  Then  Tokyo time inside <time datetime=UTC-ISO> is rendered

Scenario: naive passthrough
  Given a naive datetime
  When  ha_display runs
  Then  the output is unchanged
```

## Acceptance Criteria

- [ ] ha_pk on dict and instance
- [ ] ha_dom_token
- [ ] per-request tz
- [ ] naive passthrough
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-primarykeyinfo-codec-invalidprimarykey-and-baseadap` (st-v058-byoa-13)
- `featcore-timezones-module-and-settings-timezone` (st-v058-byoa-14)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
