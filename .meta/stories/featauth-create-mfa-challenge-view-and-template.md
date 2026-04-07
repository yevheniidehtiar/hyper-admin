---
type: story
id: lgks17PXAqL-
title: "feat(auth): create MFA challenge view and template"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:views
  - area:templates
  - area:auth
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 435
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a6f29e235576c3857e3665cd33742630b6086bbd20458918f4b4171e14d8cc72
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:39:27Z
updated_at: 2026-04-01T21:39:27Z
---

## Context

When a user with MFA enabled logs in successfully, they should be redirected to a challenge page where they enter the 6-digit code sent to their email. This modifies the login flow and adds the MFA challenge endpoint.

## Scenarios

**Scenario: successful login with MFA enabled redirects to challenge page**
  Given user alice has `mfa_enabled=True` and `mfa_method="email"`
  When  POST `/admin/login` with valid credentials
  Then  a 302 redirect to `/admin/mfa/challenge` is returned
  And   a 6-digit code is sent to alice's email

**Scenario: correct MFA code completes login**
  Given user alice is on the MFA challenge page with a valid code pending
  When  POST `/admin/mfa/challenge` with the correct code
  Then  the session is fully authenticated
  And   a 302 redirect to `/admin/` is returned

**Scenario: incorrect MFA code shows error**
  Given user alice is on the MFA challenge page
  When  POST `/admin/mfa/challenge` with an incorrect code
  Then  the MFA challenge page is re-rendered with "Invalid code" error

**Scenario: expired MFA code shows error and allows resend**
  Given user alice's code expired 1 minute ago
  When  POST `/admin/mfa/challenge` with the expired code
  Then  the error "Code expired. A new code has been sent." is shown
  And   a new code is generated and sent

## Acceptance Criteria

- [ ] `mfa_challenge_view()` handler added to `auth/views.py` (GET renders form, POST validates code)
- [ ] `mfa_challenge.html` template with code input form
- [ ] `login_view()` modified to redirect to MFA challenge when `mfa_enabled=True`
- [ ] Login stores `mfa_pending_user_id` in session (not fully authenticated yet)
- [ ] `/mfa/challenge` route registered in `core/app.py`
- [ ] `/mfa/challenge` added to `PUBLIC_SUFFIXES` in auth middleware
- [ ] Unit tests cover all 4 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/views.py`
- `src/hyperadmin/templates/mfa_challenge.html` (new)
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/auth/middleware.py`

## Dependencies
Depends on: #434 (EmailOTPService)

## Notes for Implementer
- Login flow change: authenticate -> if mfa_enabled -> store pending user in session -> redirect to challenge -> verify code -> complete login
- The user is NOT authenticated until the MFA code is verified
- Template should match login.html styling (extend `_base.html`)
- Add `data-testid="mfa-code-input"` and `data-testid="mfa-submit"` for E2E
