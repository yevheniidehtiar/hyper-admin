---
type: story
id: dHaTcZNmdauj
title: "feat(auth): create OAuthToken model"
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
  issue_number: 439
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:512174549460fde4472cf1272acb566356d8e84011dfdc78c8e5eaab3e2c25ed
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:40:22Z
updated_at: 2026-04-01T21:40:22Z
---

## Context

OAuth authentication requires storing provider tokens per user. This adds the `OAuthToken` SQLModel table to `auth/models.py`.

## Scenarios

**Scenario: OAuthToken stores provider credentials for a user**
  Given user alice authenticated via Google
  When  an OAuthToken is created with `provider="google"` and `access_token="abc123"`
  Then  the token is persisted with `user_id = alice.id`

**Scenario: OAuthToken supports multiple providers per user**
  Given user alice has a Google token
  When  a GitHub token is also created for alice
  Then  alice has 2 OAuthToken records with different providers

## Acceptance Criteria

- [ ] `OAuthToken` model added to `auth/models.py`
- [ ] Fields: `id`, `user_id` (FK), `provider` (str), `access_token`, `refresh_token`, `token_expires_at` (datetime|None), `scopes` (str|None), `created_at`, `updated_at`
- [ ] Unique constraint on `(user_id, provider)` pair
- [ ] Relationship back to User model
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/auth/models.py`
- `tests/unit/test_auth_models.py`

## Dependencies
Depends on: #438 (SDD approved)

## Notes for Implementer
- Follow existing model patterns in `auth/models.py` (User, Group, Permission)
- Use `selectin` lazy loading for the user relationship
- `access_token` and `refresh_token` are stored as plain strings in MVP (encryption is a follow-up)
- Table name: `hyperadmin_oauth_tokens`
