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

## Review amendments (2026-09-28)

- The spike has already run on fastapi 0.141.1 / starlette 1.7.0. `request.url_for("hyperadmin:user-list")` resolves from inside the sub-app, and the plain name raises `NoMatchFound`, so the fallback helper is required. A unit test pins this.
- This story ships the helpers only: `admin_url_for`, `install_namespaced_url_for` and `admin_base_path(request)` (the per-request external admin path, which honours the host's `root_path`). The 9 `request.url_for` switches in `views/dynamic.py` move to `-35`, so this story is blocked only by the gate.
- The namespace is read from `scope["hyperadmin"]`, not from `app.state`, which is now shared with the host.

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
