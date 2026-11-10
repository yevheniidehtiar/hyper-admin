---
type: story
id: R8lzBDObsA9w
title: "feat(views): RateLimitMiddleware using core protocol"
status: done
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
- [ ] Pure-ASGI `RateLimitMiddleware` calls `RateLimiter.acquire()` once per http request below the admin prefix; websocket scopes and host routes outside the prefix pass through
- [ ] Over the limit answers HTTP 429 with a `Retry-After` header, before the startup sync, session, authentication or any database work (outermost middleware)
- [ ] Configured by `rate_limit_requests` / `rate_limit_window_seconds` (`HYPERADMIN_RATE_LIMIT_*`) or `Admin(app, rate_limiter=...)` (corrected from a `HyperAdminApp` constructor, which does not exist). Off by default
- [ ] Skips static assets (`/static/` below the admin prefix)
- [ ] Per-client limit keyed by `scope["client"]`. It never reads `X-Forwarded-For`, which any client can forge; behind a proxy the server must rewrite the client address (uvicorn `--proxy-headers` with `--forwarded-allow-ips`), as the docs state
- [ ] A separate, normally stricter limit on login form POSTs (`rate_limit_login_requests`): only the MFA resend was throttled before, so password guessing was not
- [ ] All tests from #233 pass

## Files
- `src/hyperadmin/views/rate_limit.py` (new)
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/core/settings.py`

## Dependencies
- Blocked by: #234
- Blocking: D1.1
