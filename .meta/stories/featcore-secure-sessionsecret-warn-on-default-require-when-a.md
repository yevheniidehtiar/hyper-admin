---
type: story
id: U9fy1q4VPHmr
title: "feat(core): secure session_secret — warn on default, require when auth enabled"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:S
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 378
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e19bec2d4ca86a114d04ca20948ff1a5862f4cb9de6b01140b217894e6f3fa0d
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:09:19Z
updated_at: 2026-03-31T19:59:02Z
---

## Context

`core/app.py:153` has unsafe fallback `secret_key=self.session_secret or "hyperadmin-default-secret"`. With settings, this should warn in debug mode and raise in production when auth is enabled.

## Scenarios

**Scenario: warning logged when using default secret in debug mode**
  Given `settings.debug=True` and no `secret_key` set
  And   `auth_backend` is provided
  When  `Admin()` is created
  Then  a warning is logged: "Using default session secret. Set HYPERADMIN_SECRET_KEY for production."

**Scenario: error raised when auth enabled without secret in non-debug mode**
  Given `settings.debug=False` and no `secret_key` set
  And   `auth_backend` is provided
  When  `Admin()` is created
  Then  a `ValueError` is raised requiring `secret_key`

**Scenario: no warning when secret_key is explicitly set**
  Given `HyperAdminSettings(secret_key="my-production-secret")`
  And   `auth_backend` is provided
  When  `Admin()` is created
  Then  no warning or error

## Acceptance criteria

- [ ] Remove hardcoded `"hyperadmin-default-secret"` fallback
- [ ] Warn in debug mode, raise in production when auth + no secret
- [ ] No warning when secret_key is set
- [ ] Unit tests

## Files likely affected

- `src/hyperadmin/core/app.py`

## Dependencies

Depends on: #376
