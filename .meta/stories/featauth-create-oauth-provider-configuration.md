---
type: story
id: 3mu2iRMIs2uh
title: "feat(auth): create OAuth provider configuration"
status: todo
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
  issue_number: 440
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4cfdd5ee74879c0eeeb1b36f911045f7fe841589ed6f40cbfd53b9acd62c3328
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:40:36Z
updated_at: 2026-04-01T21:40:36Z
---

## Context

OAuth backends need configuration (client_id, client_secret, endpoints, scopes) for each provider. This adds `OAuthProviderConfig` and integrates it into `HyperAdminSettings`.

## Scenarios

**Scenario: Google OAuth provider is configured via settings**
  Given `HyperAdminSettings` with `oauth_providers=[OAuthProviderConfig(provider_name="google", ...)]`
  When  the settings are loaded
  Then  the Google provider config is accessible with correct `authorize_url` and `token_url`

**Scenario: missing client_id raises validation error**
  Given `OAuthProviderConfig` with `client_id=""`
  When  validation runs
  Then  a `ValueError` is raised indicating `client_id` is required

## Acceptance Criteria

- [ ] `OAuthProviderConfig` dataclass in `auth/oauth.py` (new file)
- [ ] Fields: `provider_name`, `client_id`, `client_secret`, `authorize_url`, `token_url`, `userinfo_url`, `scopes`, `redirect_uri`
- [ ] Pre-configured defaults for Google and GitHub (URLs, scopes)
- [ ] `oauth_providers: list[OAuthProviderConfig] = []` added to `HyperAdminSettings`
- [ ] Validation: `client_id` and `client_secret` required when provider present
- [ ] Unit tests cover both scenarios

## Files Likely Affected
- `src/hyperadmin/auth/oauth.py` (new)
- `src/hyperadmin/core/settings.py`
- `tests/unit/test_settings.py`

## Dependencies
Depends on: #438 (SDD approved)

## Notes for Implementer
- Google authorize URL: `https://accounts.google.com/o/oauth2/v2/auth`
- Google token URL: `https://oauth2.googleapis.com/token`
- GitHub authorize URL: `https://github.com/login/oauth/authorize`
- GitHub token URL: `https://github.com/login/oauth/access_token`
- Use Pydantic `BaseModel` for `OAuthProviderConfig` (not SQLModel — it's config, not DB)
