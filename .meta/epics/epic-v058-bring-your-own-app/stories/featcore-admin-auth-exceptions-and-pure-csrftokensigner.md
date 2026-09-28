---
type: story
id: st-v058-byoa-18
title: "feat(core): admin auth exceptions and pure CsrfTokenSigner"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:core
  - layer:domain
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Add `AdminAuthenticationRequired` and `AdminAccessDenied` to `core/auth.py`, and a pure `core/csrf.py` `CsrfTokenSigner` that uses stdlib `hmac`, `secrets` and `base64` only.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: D.1

## Files to Change

- `src/hyperadmin/core/auth.py`
- `src/hyperadmin/core/csrf.py`
- `tests/unit/test_core_csrf.py`

## Scenarios

```
Scenario: issued token validates
  Given a signer with secret S
  When  a token is issued and checked
  Then  is_valid returns True

Scenario: tampered token fails
  Given an issued token with one signature byte changed
  When  is_valid runs
  Then  False is returned

Scenario: foreign secret fails
  Given a token signed with a different secret
  When  is_valid runs
  Then  False is returned

Scenario: mismatched pair fails
  Given two different valid tokens
  When  matches(a, b) runs
  Then  False is returned
```

## Acceptance Criteria

- [ ] issued token validates
- [ ] tampered token fails
- [ ] foreign secret fails
- [ ] mismatched pair fails
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `reviewspec-approve-byoa-sdd` (st-v058-byoa-00)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
