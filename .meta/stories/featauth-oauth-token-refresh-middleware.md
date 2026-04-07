---
type: story
id: 0B4r549HlTIc
title: "feat(auth): OAuth token refresh middleware"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:M
  - area:middleware
estimate: null
epic_ref: null
github:
  issue_number: 444
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:70a3d57b0d02ac2b0c900bb51d9c1e714762358a7e0d8e63f83da211ad88e65e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:41:40Z
updated_at: 2026-04-01T21:41:40Z
---

## Context

OAuth access tokens expire. When a user with an expired token makes a request, the middleware should transparently refresh the token using the stored refresh_token. If refresh fails, the user is logged out.

## Scenarios

**Scenario: expired OAuth token is auto-refreshed**
  Given user alice's Google token expires in the past
  And   a valid `refresh_token` exists
  When  alice makes any authenticated request
  Then  the token is refreshed transparently and the request proceeds

**Scenario: refresh failure logs user out**
  Given user alice's `refresh_token` is revoked at Google
  When  alice makes an authenticated request with an expired token
  Then  alice is logged out and redirected to `/admin/login`

**Scenario: non-OAuth session users are unaffected**
  Given user bob logged in via username/password (no OAuthToken)
  When  bob makes an authenticated request
  Then  no token refresh logic executes

## Acceptance Criteria

- [ ] Token expiry check added to `AuthenticationMiddleware.dispatch()`
- [ ] Auto-refresh using stored `refresh_token` via provider's token endpoint
- [ ] Updated `access_token` and `token_expires_at` saved to `OAuthToken`
- [ ] On refresh failure: clear session, redirect to login
- [ ] Non-OAuth users skip token refresh entirely
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/middleware.py`
- `tests/unit/test_auth_middleware.py`

## Dependencies
Depends on: #443 (OAuth routes — tokens must exist first)

## Notes for Implementer
- Check for `OAuthToken` existence before attempting refresh
- Use `httpx.AsyncClient` for token refresh (same as OAuthBackend)
- Add a buffer: refresh when token expires within next 5 minutes (avoid race conditions)
- This extends existing `AuthenticationMiddleware`, not a new middleware
