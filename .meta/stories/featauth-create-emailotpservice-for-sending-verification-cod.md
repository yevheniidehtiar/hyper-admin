---
type: story
id: kHAyZyym3Iw6
title: "feat(auth): create EmailOTPService for sending verification codes"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 434
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3b99493fbda86d76fe4414ee2f7e195b94e8a3600025295309dcdfa30f1e0693
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:39:09Z
updated_at: 2026-04-01T21:39:09Z
---

## Context

MVP MFA needs a service to generate, send, and verify 6-digit OTP codes via email. This is the simplest MFA implementation — no TOTP, no QR codes, no backup codes. Session-based code storage (no Redis dependency).

## Scenarios

**Scenario: generate_code produces 6-digit numeric code**
  Given the `EmailOTPService`
  When  `generate_code()` is called
  Then  a string of exactly 6 digits is returned

**Scenario: send_code stores code in session/cache and invokes email sender**
  Given a user with email "alice@example.com"
  When  `send_code(user)` is called
  Then  a 6-digit code is stored with a 5-minute TTL
  And   the email sender is invoked with the code

**Scenario: verify_code returns True for correct code within TTL**
  Given a code "123456" was generated for user alice 2 minutes ago
  When  `verify_code(alice, "123456")` is called
  Then  it returns True
  And   the code is invalidated (single-use)

## Acceptance Criteria

- [ ] `EmailOTPService` class created in `src/hyperadmin/auth/otp.py`
- [ ] `generate_code()` returns cryptographically random 6-digit string
- [ ] `send_code(request, user)` stores code in session with 5-min TTL
- [ ] `verify_code(request, code)` validates code and invalidates after use
- [ ] `EmailSender` protocol defined for pluggable email delivery
- [ ] `ConsoleEmailSender` default (logs code to console for dev)
- [ ] Unit tests cover all 3 scenarios + expired code + wrong code

## Files Likely Affected
- `src/hyperadmin/auth/otp.py` (new)
- `tests/unit/test_otp.py` (new)

## Dependencies
Depends on: #433 (MFA fields on User model)

## Notes for Implementer
- Use `secrets.randbelow(1000000)` for code generation, zero-pad to 6 digits
- Session keys: `mfa_code`, `mfa_code_expires`, `mfa_pending_user_id`
- TTL check: compare `datetime.now()` against `mfa_code_expires`
- After successful verify, clear all `mfa_*` session keys
- `EmailSender` protocol: `async def send(to: str, subject: str, body: str) -> None`
