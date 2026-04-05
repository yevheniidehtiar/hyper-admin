---
type: story
id: tcJSrTKL1HhE
title: "feat(auth): wire MFA into login flow + enable/disable settings"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - frontend
  - size:M
  - planned
  - auth
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 487
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f00a903c98cf1ad16b23f8570b04b6d1c4856c658595e56c0c20c613c2400ae5
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-04T18:35:59Z
updated_at: 2026-04-04T18:35:59Z
---


## Summary

Wire the MFA challenge into the existing login flow: after successful password authentication, check if user has mfa_enabled and redirect to challenge page instead of completing login. Also add MFA enable/disable settings view.

## Files to Change

- `src/hyperadmin/auth/views.py` — modify `login_view` to check mfa_enabled
- `src/hyperadmin/auth/middleware.py` — handle partial-auth session state
- `src/hyperadmin/templates/auth/mfa_settings.html` — new template

## Scenarios

**Scenario: MFA-enabled user redirected to challenge after password**
  Given user "alice" has mfa_enabled=True
  When  POST /admin/login with correct username and password
  Then  password is verified but session is NOT fully created
  And   redirect to /admin/mfa/challenge

**Scenario: MFA-disabled user logs in normally**
  Given user "bob" has mfa_enabled=False
  When  POST /admin/login with correct credentials
  Then  session is created and redirect to /admin/

**Scenario: enable MFA from settings**
  Given user "alice" is logged in and visits /admin/mfa/settings
  When  clicks "Enable MFA"
  Then  OTP code is sent to alice's email
  And   after verification, mfa_enabled is set to True

**Scenario: disable MFA from settings**
  Given user "alice" has mfa_enabled=True and visits /admin/mfa/settings
  When  clicks "Disable MFA" and confirms
  Then  mfa_enabled is set to False

**Scenario: partial-auth state cannot access admin routes**
  Given user "alice" submitted correct password but hasn't completed MFA
  When  navigating to /admin/order
  Then  redirect to /admin/mfa/challenge (not the admin page)

## Acceptance Criteria

- [ ] Login view checks mfa_enabled after password verification
- [ ] Partial-auth session state prevents admin access until MFA completes
- [ ] MFA settings view allows enable/disable
- [ ] Enable flow sends verification code
- [ ] Disable flow requires confirmation
- [ ] Middleware enforces full auth (password + MFA) for admin routes

## Blocked by

- BATCH:01 (MFA challenge view)

## Parent

- Epic: #473
