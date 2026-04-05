---
type: story
id: 9hEwtOTWxN5b
title: "feat(auth): create structured auth exceptions"
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
  issue_number: 442
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:02fff35416b9e8f7d6694d6202d3e49c6e7ff149248916f3c89e02e8834ce548
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:41:08Z
updated_at: 2026-04-01T21:41:08Z
---

## Context

OAuth and MFA flows need structured exceptions for proper error handling and flow control. Currently there are no auth-specific exception classes.

## Scenarios

**Scenario: OAuthProviderError carries provider name and detail**
  Given an OAuth failure from Google
  When  `OAuthProviderError("google", "Token exchange failed")` is raised
  Then  `str(exc)` contains "google" and "Token exchange failed"

**Scenario: MFARequiredError carries the user and redirect URL**
  Given user alice requires MFA
  When  `MFARequiredError(user=alice, redirect="/admin/mfa/challenge")` is raised
  Then  `exc.user` is alice and `exc.redirect` is "/admin/mfa/challenge"

## Acceptance Criteria

- [ ] `auth/exceptions.py` created with: `OAuthProviderError`, `MFARequiredError`, `OAuthConfigError`
- [ ] Each exception carries structured context (provider, detail, user, redirect)
- [ ] Unit tests cover both scenarios
- [ ] Exceptions are importable from `hyperadmin.auth.exceptions`

## Files Likely Affected
- `src/hyperadmin/auth/exceptions.py` (new)
- `tests/unit/test_auth_exceptions.py` (new)

## Dependencies
Depends on: #438 (SDD approved)

## Notes for Implementer
- Follow Python exception best practices: inherit from a base `HyperAdminAuthError`
- Keep them simple: no business logic in exception classes
