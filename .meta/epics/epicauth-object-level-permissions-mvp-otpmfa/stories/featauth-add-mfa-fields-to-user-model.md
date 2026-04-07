---
type: story
id: D5j6fmfAwPOj
title: "feat(auth): add MFA fields to User model"
status: todo
priority: medium
assignee: null
labels:
  - backend
  - size:S
  - planned
  - auth
estimate: null
epic_ref:
  id: mmZ2u_cMD2xN
github:
  issue_number: 483
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:378d2ffe80fe187b3d7af53806be0594cd65e6056eb1befc4e3d494d70febd21
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-02T14:53:01Z
updated_at: 2026-04-02T14:53:02Z
---

## Summary

Add MFA-related fields to the `User` model to support email-based OTP authentication.

## Files to Change

- `src/hyperadmin/auth/models.py` — add fields to `User`

## Design

New fields on `User`:
```python
mfa_enabled: bool = Field(default=False)
mfa_method: str | None = Field(default=None)  # "email" for MVP, extensible later
```

## Scenarios

**Scenario: new user has MFA disabled by default**
  Given a new User record is created
  When  the user's fields are inspected
  Then  `mfa_enabled` is `False` and `mfa_method` is `None`

**Scenario: MFA fields are persisted**
  Given user "alice" enables MFA with method "email"
  When  the user record is saved and reloaded
  Then  `mfa_enabled` is `True` and `mfa_method` is `"email"`

## Acceptance Criteria

- [ ] `mfa_enabled` bool field added with default False
- [ ] `mfa_method` optional string field added with default None
- [ ] Backward compatible (no migration required — new fields have defaults)

## Blocked by

- #475 (spec approval)

## Parent

- Epic: #473
