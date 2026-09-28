---
type: story
id: st-v058-byoa-34
title: "feat(views): namespace-aware url helper and Jinja url_for override"
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

**Start with a spike test** that asserts `url_for('hyperadmin:static', ...)` and `hyperadmin:user-detail` resolve through a mounted FastAPI sub-app. If the spike fails, stop and escalate (risk fallback). Then add `views/urls.py` with `admin_url_for` and `install_namespaced_url_for`, and switch the 9 `request.url_for` sites in `views/dynamic.py`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.1

## Files to Change

- `src/hyperadmin/views/urls.py`
- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_admin_urls.py`

## Scenarios

```
Scenario: namespaced route resolves
  Given a sub-app mounted with name 'hyperadmin'
  When  admin_url_for(request, 'user-list') runs
  Then  '/admin/user' is returned

Scenario: host route names still resolve
  Given a host route named 'reports'
  When  a template calls url_for('reports')
  Then  the host URL is rendered
```

## Acceptance Criteria

- [ ] namespaced route resolves
- [ ] host route names still resolve
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `refactorviews-bulk-ids-single-actions-and-popup-payload-are` (st-v058-byoa-30)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
