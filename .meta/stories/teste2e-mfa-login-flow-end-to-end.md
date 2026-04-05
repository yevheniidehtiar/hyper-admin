---
type: story
id: CXW0q4r9iP5_
title: "test(e2e): MFA login flow end-to-end"
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
  issue_number: 437
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:054d56269d0f668ad6a98506b171953545aa998e68f90044275ea20c10d40fdf
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:39:54Z
updated_at: 2026-04-01T21:39:54Z
---

## Context

End-to-end Playwright tests for the full MFA flow: login with MFA, code challenge, MFA enable/disable from settings.

## Scenarios

**Scenario: full MFA login flow with email OTP**
  Given user alice has MFA enabled via email
  When  alice logs in with valid credentials
  Then  she is redirected to the MFA challenge page
  And   after entering the correct code, she reaches the dashboard

**Scenario: MFA enable flow from settings**
  Given user alice is logged in with MFA disabled
  When  she navigates to MFA settings and enables email MFA
  Then  MFA is activated after code verification

**Scenario: login without MFA goes directly to dashboard**
  Given user bob has MFA disabled
  When  bob logs in with valid credentials
  Then  he is redirected directly to the dashboard (no MFA challenge)

## Acceptance Criteria

- [ ] E2E test app with MFA-enabled and MFA-disabled users
- [ ] All 3 scenarios pass as Playwright tests
- [ ] Tests use `ConsoleEmailSender` and extract code from logs/session
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Accessibility-first selectors

## Files Likely Affected
- `tests/e2e/test_mfa_flow.py` (new)
- `tests/e2e/conftest.py` (fixture for MFA-enabled app)

## Dependencies
Depends on: #436 (MFA settings view)

## Notes for Implementer
- For E2E tests, use `ConsoleEmailSender` and intercept the code via app state or session
- Alternative: expose a test-only endpoint that returns the current OTP code
- Follow patterns in `tests/e2e/test_auth_flow.py`
