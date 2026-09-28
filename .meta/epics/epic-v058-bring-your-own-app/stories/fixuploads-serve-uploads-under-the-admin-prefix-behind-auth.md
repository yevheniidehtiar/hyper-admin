---
type: story
id: st-v058-byoa-37
title: "fix(uploads): serve uploads under the admin prefix behind auth with a nosniff/attachment policy"
status: todo
priority: high
assignee: null
labels:
  - size:M
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

Remove the public `/uploads` mount at the root. Add `views/uploads.py`, which streams from storage with a traversal check, `nosniff`, `CSP: sandbox`, and `attachment` for everything except an image allow-list (no SVG). `detail.html` uses `url_for('uploads')`. `public_uploads_path` is the escape hatch.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: C.5

## Files to Change

- `src/hyperadmin/views/uploads.py`
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/core/settings.py`
- `src/hyperadmin/templates/detail.html`
- `tests/unit/test_upload_serving.py`

## Scenarios

```
Scenario: uploads require authentication
  Given auth enabled
  When  an anonymous GET /admin/uploads/a.pdf is made
  Then  it redirects to /admin/login

Scenario: not served at root
  Given file storage configured
  When  GET /uploads/a.pdf is requested
  Then  the status is 404

Scenario: SVG downloaded
  Given an authenticated user and x.svg
  When  GET /admin/uploads/x.svg is requested
  Then  Content-Disposition is attachment
  And   nosniff is set

Scenario: traversal rejected
  Given an authenticated user
  When  GET /admin/uploads/..%2F..%2Fetc%2Fpasswd is requested
  Then  the status is 404
```

## Acceptance Criteria

- [ ] uploads require authentication
- [ ] not served at root
- [ ] SVG downloaded
- [ ] traversal rejected
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-isolated-sub-application-mount` (st-v058-byoa-35)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
