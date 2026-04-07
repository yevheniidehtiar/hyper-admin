---
type: story
id: lMitnJy49VpS
title: "feat(auth): add OAuth2 routes"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:auth
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 443
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5d5df593bccfbaa6e071711d339a5ea8ee908c2e45342647acc5937054ddd61c
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:41:24Z
updated_at: 2026-04-01T21:41:24Z
---

## Context

OAuth requires authorize and callback endpoints for each provider. This adds the route handlers and wires them into the admin app.

## Scenarios

**Scenario: GET /oauth/authorize/google redirects to Google consent screen**
  Given Google OAuth is configured with `client_id` and scopes
  When  GET `/admin/oauth/authorize/google`
  Then  a 302 redirect to `accounts.google.com/o/oauth2/auth` with correct params

**Scenario: GET /oauth/callback/google with valid code logs user in**
  Given a valid authorization code is returned from Google
  When  GET `/admin/oauth/callback/google?code=abc123&state=xyz`
  Then  the user is provisioned/linked, session is created
  And   redirect to `/admin/`

**Scenario: GET /oauth/callback/google with error shows login page error**
  Given Google returns `error=access_denied`
  When  GET `/admin/oauth/callback/google?error=access_denied`
  Then  redirect to `/admin/login` with error message

**Scenario: GET /oauth/authorize/unknown returns 404**
  Given no provider named "unknown" is configured
  When  GET `/admin/oauth/authorize/unknown`
  Then  response is 404

## Acceptance Criteria

- [ ] `oauth_authorize_view(provider)` handler — builds authorize URL with state, redirects
- [ ] `oauth_callback_view(provider)` handler — exchanges code, provisions user, creates session
- [ ] CSRF state parameter generated and validated
- [ ] Routes registered: `/oauth/authorize/{provider}`, `/oauth/callback/{provider}`
- [ ] OAuth paths added to `PUBLIC_SUFFIXES` in auth middleware
- [ ] If MFA enabled on provisioned user, redirect to MFA challenge
- [ ] Unit tests cover all 4 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/views.py`
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/auth/middleware.py`

## Dependencies
Depends on: #441 (OAuthBackend), #442 (auth exceptions)

## Notes for Implementer
- State parameter: generate random string, store in session, validate on callback
- The authorize URL must include: client_id, redirect_uri, response_type=code, scope, state
- On callback: exchange code -> get userinfo -> provision user -> login -> redirect
- If user has `mfa_enabled=True`, redirect to `/admin/mfa/challenge` instead of dashboard
