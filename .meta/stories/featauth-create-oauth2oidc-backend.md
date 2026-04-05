---
type: story
id: ZgdBgtQP_qnl
title: "feat(auth): create OAuth2/OIDC backend"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:L
estimate: null
epic_ref: null
github:
  issue_number: 441
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7c95729e8e2692405740258d64d3a85dee5698c17ebaa47b545360a9a1cc7ea4
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:40:56Z
updated_at: 2026-04-01T21:40:56Z
---

## Context

The core OAuth backend that handles token exchange, userinfo retrieval, and user provisioning for Google and GitHub. Implements the `AuthBackend` protocol pattern.

## Scenarios

**Scenario: exchange_code returns access_token from Google**
  Given a valid authorization code from Google OAuth
  When  `exchange_code(code, redirect_uri)` is called
  Then  an `access_token` and `refresh_token` are returned

**Scenario: get_userinfo returns user profile from Google**
  Given a valid `access_token` for Google
  When  `get_userinfo(access_token)` is called
  Then  the user's email, name, and picture URL are returned

**Scenario: provision_user creates new user on first OAuth login**
  Given no user exists with email "alice@gmail.com"
  When  `provision_user(userinfo)` is called
  Then  a new User is created with `email="alice@gmail.com"`, `is_active=True`
  And   an OAuthToken is created linking the user to the Google provider

**Scenario: provision_user links existing user on subsequent OAuth login**
  Given user alice already exists with email "alice@gmail.com"
  When  `provision_user(userinfo)` is called for alice's Google login
  Then  the existing User is returned
  And   the OAuthToken is updated with new access_token

**Scenario: exchange_code handles invalid authorization code**
  Given an expired or invalid authorization code
  When  `exchange_code(code, redirect_uri)` is called
  Then  an `OAuthProviderError` is raised

**Scenario: GitHub provider uses correct token exchange endpoint**
  Given a GitHub OAuth provider configuration
  When  `exchange_code()` is called with a GitHub code
  Then  the request is sent to `https://github.com/login/oauth/access_token`

## Acceptance Criteria

- [ ] `OAuthBackend` class in `auth/oauth.py`
- [ ] `exchange_code(provider_config, code, redirect_uri)` → token dict
- [ ] `get_userinfo(provider_config, access_token)` → userinfo dict
- [ ] `provision_user(engine, provider_name, userinfo)` → User (create or link)
- [ ] Uses `httpx.AsyncClient` for HTTP calls (already a dependency)
- [ ] Google and GitHub provider-specific handling (different userinfo formats)
- [ ] Unit tests with mocked HTTP responses for all 6 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/oauth.py`
- `tests/unit/test_oauth_backend.py` (new)

## Dependencies
Depends on: #439 (OAuthToken model), #440 (OAuthProviderConfig)

## Notes for Implementer
- Use `httpx.AsyncClient` for token exchange and userinfo calls
- GitHub returns `access_token` in form-encoded body (set `Accept: application/json` header)
- Google returns standard JSON response
- User provisioning: match by email first, create if not found
- Generate a random password hash for OAuth-provisioned users (they don't use password login)
- This is `size:L` — consider an SDD section in the epic SDD
