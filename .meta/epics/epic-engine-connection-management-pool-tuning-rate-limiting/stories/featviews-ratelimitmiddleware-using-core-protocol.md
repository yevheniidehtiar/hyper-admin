---
type: story
id: R8lzBDObsA9w
title: "feat(views): RateLimitMiddleware using core protocol"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:views
  - size:M
  - area:middleware
  - performance
estimate: null
epic_ref:
  id: ed1DCvpnaZ1w
github:
  issue_number: 235
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:eb0575afa166aaca1c6797a746beee9775385b6989f31eaa3ce3486f57130d5d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:32Z
updated_at: 2026-03-29T18:26:21Z
---

## Context
Part of Epic #212 (B2: Rate limiting middleware).

## Acceptance criteria
- [ ] ASGI middleware that checks `RateLimiter.is_allowed()` on each request
- [ ] Returns HTTP 429 with Retry-After header when rate exceeded
- [ ] Configurable via `HyperAdminApp` constructor: `rate_limiter: RateLimiter | None = None`
- [ ] Skips static asset paths (e.g., `/static/`)
- [ ] Per-IP rate limiting using client IP from request
- [ ] All tests from B2.1 pass

## Files
- `src/hyperadmin/views/middleware.py` (new)
- `src/hyperadmin/core/app.py`

## Dependencies
- Blocked by: #234 (B2.2 core protocol)
- Blocking: D1.1
