---
type: story
id: _m2CkJKkcLig
title: "test(e2e): OAuth login flow end-to-end"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 446
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a411c7a7112eaccf885d7bcd63f2c93cb04601514bfe418fcee51e18b43456fc
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:42:07Z
updated_at: 2026-04-01T21:42:07Z
---

## Context

End-to-end Playwright tests verifying OAuth login buttons, redirect flow, and callback handling with mock OAuth providers.

## Scenarios

**Scenario: OAuth login button redirects to provider**
  Given Google OAuth is configured
  When  user clicks "Sign in with Google"
  Then  the browser navigates to the Google authorization URL

**Scenario: OAuth callback creates user and session**
  Given a mock OAuth callback with valid code
  When  the callback URL is visited
  Then  the user is created and redirected to the dashboard

**Scenario: OAuth login with MFA enabled triggers MFA challenge**
  Given user alice logged in via Google with MFA enabled
  When  the OAuth callback completes
  Then  alice is redirected to the MFA challenge page

## Acceptance Criteria

- [ ] E2E test app with mock OAuth provider (intercept HTTP calls)
- [ ] All 3 scenarios pass as Playwright tests
- [ ] Mock provider returns configurable userinfo
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Accessibility-first selectors

## Files Likely Affected
- `tests/e2e/test_oauth_flow.py` (new)
- `tests/e2e/conftest.py`

## Dependencies
Depends on: #445 (OAuth login buttons on UI)

## Notes for Implementer
- Mock the OAuth provider by intercepting `httpx` calls or using a local test server
- For the redirect test, verify the URL contains the expected OAuth params
- For callback test, simulate a valid callback URL with code parameter
