---
type: story
id: 2oEQJgw7Zd_9
title: "feat(auth): add MFA fields to User model"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 433
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:953a5e2a112620e0c184fa8e4a830ec03c46b5b2f277820fc7783250aa005212
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:38:51Z
updated_at: 2026-04-01T21:38:51Z
---

## Context

The User model has no MFA-related fields. To support MVP email-based OTP, we need `mfa_enabled` and `mfa_method` columns on the User table.

## Scenarios

**Scenario: new User has MFA disabled by default**
  Given a newly created User
  When  the user's `mfa_enabled` field is inspected
  Then  it is `False` and `mfa_method` is `None`

**Scenario: User can enable email MFA**
  Given an existing User
  When  `mfa_enabled` is set to `True` and `mfa_method` is set to `"email"`
  Then  the fields are persisted correctly

## Acceptance Criteria

- [ ] `mfa_enabled: bool = Field(default=False)` added to User model
- [ ] `mfa_method: str | None = Field(default=None, max_length=20)` added to User model
- [ ] Database table updated (create_tables auto-migration)
- [ ] Existing auth tests pass (backward compatible)
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/auth/models.py`
- `tests/unit/test_auth_models.py`

## Dependencies
Depends on: #423 (SDD approved)

## Notes for Implementer
- Add fields after `is_superuser` in the User model for logical grouping
- `mfa_method` is a simple string field, not an enum — allows future extensibility ("email", "totp", etc.)
- MVP only supports "email" as mfa_method
