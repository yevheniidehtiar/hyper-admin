---
type: story
id: NXwMsez7DP7d
title: "feat(auth): add MFA enable/disable settings view"
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
  issue_number: 436
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1a7e7805a6bc611ca17b9276017d8921859ef8fd7a97cab1ee85ae75cd81f8e8
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:39:41Z
updated_at: 2026-04-01T21:39:41Z
---

## Context

Users need a way to enable and disable MFA from within the admin interface. This adds a settings page where authenticated users can toggle email-based MFA.

## Scenarios

**Scenario: user enables MFA via email**
  Given user alice has `mfa_enabled=False`
  When  POST `/admin/mfa/settings` with `action="enable"` and `method="email"`
  Then  a verification code is sent to alice's email
  And   after entering the correct code, `mfa_enabled=True` and `mfa_method="email"`

**Scenario: user disables MFA**
  Given user alice has `mfa_enabled=True`
  When  POST `/admin/mfa/settings` with `action="disable"`
  Then  `mfa_enabled` is set to False and `mfa_method` is set to None

**Scenario: MFA settings page shows current status**
  Given user alice has `mfa_enabled=True`, `mfa_method="email"`
  When  GET `/admin/mfa/settings`
  Then  the page shows "MFA is enabled via email" with a "Disable" button

## Acceptance Criteria

- [ ] `mfa_settings_view()` handler in `auth/views.py` (GET shows status, POST toggles)
- [ ] `mfa_settings.html` template with enable/disable form
- [ ] Enable flow: send code -> verify -> set `mfa_enabled=True`
- [ ] Disable flow: immediate (no code required for disable)
- [ ] Route `/mfa/settings` registered in `core/app.py`
- [ ] Link to MFA settings added to navbar or user menu
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/views.py`
- `src/hyperadmin/templates/mfa_settings.html` (new)
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/templates/_navbar.html` (link to settings)

## Dependencies
Depends on: #435 (MFA challenge view — reuses code verification flow)

## Notes for Implementer
- Enabling MFA requires email verification (send code, then verify)
- Disabling MFA is immediate — no code required (user is already authenticated)
- Store `mfa_enabled` and `mfa_method` on the User model (via adapter update)
