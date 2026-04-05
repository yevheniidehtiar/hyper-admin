---
type: story
id: tXtXyvPqaeNY
title: "feat(auth): create TenantMiddleware for tenant resolution"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:auth
  - size:M
  - area:middleware
estimate: null
epic_ref: null
github:
  issue_number: 449
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:fcaafe2b8e311d81031354213f8ea16584585fd4da074d60db0dd0368466c252
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:42:38Z
updated_at: 2026-04-01T21:42:38Z
---

## Context

The `TenantAwareAdapterMixin` (#448) reads `request.state.tenant_id`. A middleware is needed to populate this value from the user profile, a header, or subdomain.

## Scenarios

**Scenario: TenantMiddleware extracts tenant_id from user profile**
  Given user alice has `tenant_id = 42` in her profile
  When  any authenticated request is processed
  Then  `request.state.tenant_id = 42`

**Scenario: TenantMiddleware extracts tenant_id from X-Tenant-ID header**
  Given the request includes header `X-Tenant-ID: 42`
  When  the middleware processes the request
  Then  `request.state.tenant_id = 42`

**Scenario: missing tenant_id returns 400 when tenant enforcement is enabled**
  Given tenant enforcement is enabled and no `tenant_id` can be resolved
  When  any request is processed
  Then  response is 400 "Tenant context required"

## Acceptance Criteria

- [ ] `TenantMiddleware` class in `auth/middleware.py`
- [ ] Resolution order: user profile field → HTTP header → 400 error
- [ ] Configurable header name (default: `X-Tenant-ID`)
- [ ] Configurable user field name (default: `tenant_id`)
- [ ] Optional enforcement (skip for non-admin routes)
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/auth/middleware.py`
- `tests/unit/test_auth_middleware.py`

## Dependencies
Depends on: #448 (TenantAwareAdapterMixin)

## Notes for Implementer
- Add as separate middleware class, not merged into AuthenticationMiddleware
- Only activate when `tenant_enabled=True` in settings
- For MVP, focus on user profile and header resolution (subdomain is a follow-up)
