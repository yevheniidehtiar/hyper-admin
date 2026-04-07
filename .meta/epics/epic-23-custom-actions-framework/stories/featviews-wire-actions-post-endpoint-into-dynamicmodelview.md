---
type: story
id: HGsyYUmH9v_V
title: "feat(views): wire actions POST endpoint into DynamicModelView"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:views
  - size:M
estimate: null
epic_ref:
  id: kR3DYwg4B6e2
github:
  issue_number: 186
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4ad2053568e0e48a73b8291845f6bcdaab76fb72bfc9dea0c034ae09d471e854
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:34:14Z
updated_at: 2026-03-28T19:44:47Z
---

> **Part of:** #41
> **Depends on:** #184

## Acceptance Criteria
- [ ] `POST /admin/{model_name}/{id}/action/{action_name}` registered in `routing.py`
- [ ] `DynamicModelView.run_action()` dispatches to registered `ActionDef` handler
- [ ] Returns HTMX redirect on success; 404 if action not found; 403 if unauthorized
- [ ] Reuses existing `_check_permission()` pattern

## Files
- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/routing.py`

