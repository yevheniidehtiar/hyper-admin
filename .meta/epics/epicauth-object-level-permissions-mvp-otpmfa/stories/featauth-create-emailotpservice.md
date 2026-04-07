---
type: story
id: kdjNeiFT6qZq
title: "feat(auth): create EmailOTPService"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:M
  - planned
  - auth
estimate: null
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 484
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:589640e149c1f1f5f6e0f0bae5657008357f118ba46d7d143ca5117066cd8b3b
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T14:53:54Z
updated_at: 2026-04-02T14:53:54Z
---

## Summary

Create the `EmailOTPService` that generates, stores, and verifies 6-digit one-time passwords sent via email. This is the backend for MVP MFA.

## Files to Change

- `src/hyperadmin/auth/otp.py` — new file

## Design

```python
class EmailOTPService:
    def __init__(self, email_sender: Callable, ttl_seconds: int = 300):
        ...
    
    async def generate_and_send(self, user: User) -> None:
        """Generate 6-digit OTP, store in session/cache, send via email."""
    
    async def verify(self, user: User, code: str, session: dict) -> bool:
        """Verify OTP code. Returns True if valid and not expired."""
```

- OTP is a 6-digit numeric string (e.g., "482931")
- Stored in session state (keyed by user ID) with timestamp
- Default TTL: 5 minutes
- Rate limit: max 3 codes per 10 minutes per user
- `email_sender` is a pluggable callable — Admin provides the implementation

## Scenarios

**Scenario: generate and send OTP code**
  Given user "alice" with email "alice@example.com"
  When  `generate_and_send(alice)` is called
  Then  a 6-digit code is generated and stored
  And   email_sender is called with alice's email and the code

**Scenario: verify valid OTP code**
  Given user "alice" has a pending OTP code "123456" generated 2 minutes ago
  When  `verify(alice, "123456", session)` is called
  Then  result is `True`

**Scenario: reject expired OTP code**
  Given user "alice" has a pending OTP code generated 6 minutes ago (TTL=300s)
  When  `verify(alice, code, session)` is called
  Then  result is `False`

**Scenario: reject wrong OTP code**
  Given user "alice" has a pending OTP code "123456"
  When  `verify(alice, "999999", session)` is called
  Then  result is `False`

**Scenario: rate limit exceeded**
  Given user "alice" has requested 3 OTP codes in the last 10 minutes
  When  `generate_and_send(alice)` is called again
  Then  raises `RateLimitError`

## Acceptance Criteria

- [ ] Generates 6-digit numeric codes
- [ ] Stores OTP with timestamp in session
- [ ] Verifies code + expiry
- [ ] Rejects expired codes
- [ ] Rejects wrong codes
- [ ] Rate limiting (3 per 10 min)
- [ ] Pluggable email_sender callable

## Blocked by

- #483 (User MFA fields)

## Parent

- Epic: #473
