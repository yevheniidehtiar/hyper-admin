---
type: story
id: K_yj-f9GF-MM
title: "feat(views): auth integration for JSON API (session + optional bearer token)"
status: todo
priority: medium
assignee: null
labels:
  - area:auth
  - size:M
estimate: null
epic_ref:
  id: y5VW2cjEfD85
github:
  issue_number: 200
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3b60400fae8aec573469cb6389c64e86e5838c05c276aa8aee14f2d77794aeda
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-25T13:41:57Z
updated_at: 2026-03-30T20:51:50Z
---

> **Part of:** #76
> **Depends on:** #199

## Acceptance Criteria
- [ ] JSON API endpoints reuse existing session cookie auth middleware
- [ ] Optional bearer token support (enabled via `Admin(enable_api_token_auth=True)`)
- [ ] 401 returned when unauthenticated; 403 when permission denied
- [ ] Auth layer tested independently of endpoint logic

## Files
- `src/hyperadmin/views/json_api.py`
- `src/hyperadmin/auth/middleware.py`

