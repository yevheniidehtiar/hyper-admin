---
type: story
id: 1ZL3v9sZ7Ud0
title: "test: unit + e2e tests for MFA login flow"
status: todo
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - auth
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 488
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c5a11fccd6d4e47f2fed1d00a23764cf9e36bc49fc64e23af16452229b377d14
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-04T18:36:02Z
updated_at: 2026-04-04T18:36:02Z
---


## Summary

Comprehensive test coverage for the email OTP MFA flow: unit tests for EmailOTPService and E2E tests for the full login-with-MFA flow.

## Files to Change

- `tests/unit/test_email_otp.py` — new
- `tests/e2e/test_mfa_login.py` — new

## Scenarios

**Scenario: unit — OTP generation produces 6-digit code**
  Given EmailOTPService is configured
  When  generate_and_send is called
  Then  code is a 6-digit numeric string

**Scenario: unit — expired code rejected**
  Given OTP was generated 6 minutes ago (TTL=300s)
  When  verify is called
  Then  result is False

**Scenario: e2e — MFA-enabled user completes two-step login**
  Given user "alice" has mfa_enabled=True
  When  alice submits correct password on login page
  Then  redirected to MFA challenge page
  When  alice enters the correct OTP code
  Then  redirected to admin dashboard

**Scenario: e2e — wrong OTP shows error and allows retry**
  Given user "alice" is on MFA challenge page
  When  alice enters wrong code "000000"
  Then  error message is shown
  And   alice can enter the correct code and proceed

**Scenario: e2e — MFA-disabled user skips challenge**
  Given user "bob" has mfa_enabled=False
  When  bob submits correct password on login page
  Then  redirected directly to admin dashboard (no MFA challenge)

## Acceptance Criteria

- [ ] Unit tests for OTP generation, verification, expiry, rate limiting
- [ ] E2E test: full MFA login flow (password -> challenge -> dashboard)
- [ ] E2E test: wrong code -> retry -> success
- [ ] E2E test: non-MFA user skips challenge
- [ ] All tests pass

## Blocked by

- BATCH:02 (wire MFA into login flow)

## Parent

- Epic: #473
