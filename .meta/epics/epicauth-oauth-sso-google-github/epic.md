---
type: epic
id: lY8FzwA2boNK
title: "epic(auth): OAuth SSO — Google & GitHub"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:core
  - area:auth
  - roadmap
milestone_ref: null
github:
  issue_number: 420
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9ed270d8025b1e3289b0d9cd86d88843484c94faa133daa0d5f96342e7edd024
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:35:53Z
updated_at: 2026-04-01T21:46:25Z
---

## Overview

Implement OAuth2/OIDC authentication backends for Google and GitHub SSO.

**Milestone**: v0.5.2 — OAuth SSO  
**SDD Required**: Yes — `docs/specs/oauth-sso.md`  
**Modules affected**: auth/, core/, views/  
**Depends on**: Epic #419 (Object Permissions & MFA) — AuthBackend protocol must be stable

### What's included

- `OAuthToken` model (provider, tokens, scopes)
- `OAuthProviderConfig` dataclass + settings integration
- `OAuthBackend` implementing AuthBackend protocol (Google, GitHub)
- Structured auth exceptions (`OAuthProviderError`, `MFARequiredError`)
- OAuth routes (`/oauth/authorize/{provider}`, `/oauth/callback/{provider}`)
- OAuth token refresh middleware
- OAuth login buttons on login page
- E2E tests

### NOT included (deferred)
- SAML2 (too complex for MVP)
- Provider-specific logout
- Session revocation endpoints

### Dependency DAG

```
#438 (spec) ──┬──► #439 ──┐
              ├──► #440 ──┼──► #441 ──┐
              └──► #442 ──┘           │
                                      ▼
                                  #443 ──┬──► #444
                                         └──► #445 → #446
```

## Tasks
- [ ] #438 — review(spec): approve SDD for OAuth SSO
- [ ] #439 — feat(auth): create OAuthToken model
- [ ] #440 — feat(auth): create OAuth provider configuration
- [ ] #441 — feat(auth): create OAuth2/OIDC backend
- [ ] #442 — feat(auth): create structured auth exceptions
- [ ] #443 — feat(auth): add OAuth2 routes
- [ ] #444 — feat(auth): OAuth token refresh middleware
- [ ] #445 — feat(ui): add OAuth login buttons to login page
- [ ] #446 — test(e2e): OAuth login flow end-to-end
