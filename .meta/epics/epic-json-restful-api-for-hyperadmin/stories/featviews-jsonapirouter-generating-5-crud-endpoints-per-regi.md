---
type: story
id: y6RqfNvYELxa
title: "feat(views): JsonApiRouter generating 5 CRUD endpoints per registered model"
status: todo
priority: medium
assignee: null
labels:
  - area:views
  - size:L
estimate: null
epic_ref:
  id: y5VW2cjEfD85
github:
  issue_number: 199
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c40a2aee600710ad2795531a0a61505f62eaa9fc5d63b033fbb61d925c34a785
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:41:55Z
updated_at: 2026-03-30T20:51:50Z
---

> **Part of:** #76
> **Depends on:** #197

## Acceptance Criteria
- [ ] `src/hyperadmin/views/json_api.py` (new): `JsonApiRouter` class
- [ ] Auto-generates per registered model: `GET /api/{model}?page=&page_size=&search=`, `POST /api/{model}/`, `GET /api/{model}/{id}`, `PUT /api/{model}/{id}`, `DELETE /api/{model}/{id}`
- [ ] Registered alongside HTML routes in `routing.py`
- [ ] All endpoints appear in FastAPI `/docs` with correct response models
- [ ] Pagination: default `page_size=50`, max 200

## Files
- `src/hyperadmin/views/json_api.py` (new)
- `src/hyperadmin/routing.py`

