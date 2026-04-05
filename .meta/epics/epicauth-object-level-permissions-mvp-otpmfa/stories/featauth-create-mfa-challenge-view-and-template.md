---
type: story
id: iFLPQ-HEoWFU
title: "feat(auth): create MFA challenge view and template"
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
  issue_number: 486
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c71c32b82ad2ae8679794de9c5b104d0eff27313fb1f514b8f080dd14282705d
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-04T18:35:56Z
updated_at: 2026-04-04T18:35:56Z
---


## Summary

Create the MFA challenge view that prompts the user to enter the 6-digit OTP code sent to their email after successful password authentication.

## Files to Change

- `src/hyperadmin/auth/views.py` — add `mfa_challenge_view`, `mfa_verify_view`
- `src/hyperadmin/templates/auth/mfa_challenge.html` — new template

## Scenarios

**Scenario: MFA challenge page renders with code input**
  Given user "alice" passed password authentication and has mfa_enabled=True
  When  GET /admin/mfa/challenge
  Then  page renders a form with a 6-digit code input and "Verify" button

**Scenario: correct OTP code completes login**
  Given user "alice" is on MFA challenge page and code "123456" was sent
  When  POST /admin/mfa/verify with code=123456
  Then  session is created and redirect to /admin/

**Scenario: wrong OTP code shows error**
  Given user "alice" is on MFA challenge page
  When  POST /admin/mfa/verify with code=999999
  Then  error "Invalid code" is shown and user stays on challenge page

**Scenario: expired OTP code shows error with resend option**
  Given user "alice" has an OTP code that expired
  When  POST /admin/mfa/verify with the expired code
  Then  error "Code expired, please request a new one" is shown
  And   a "Resend code" link is available

## Acceptance Criteria

- [ ] MFA challenge GET endpoint renders code input form
- [ ] MFA verify POST endpoint validates code via EmailOTPService
- [ ] Successful verification creates session and redirects
- [ ] Failed verification shows error and stays on page
- [ ] Resend code link triggers new OTP generation

## Blocked by

- #484 (EmailOTPService)

## Parent

- Epic: #473
