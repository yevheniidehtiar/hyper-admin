---
type: story
id: t4NqU5jku3Pd
title: "test: unit tests for multi-tenant filtering"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 451
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b7941259cbec0f7af7a01770b88ff41a29db4d1f6ab18fb618aa1c2fb439557e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:43:01Z
updated_at: 2026-04-01T21:43:01Z
---

## Context

Comprehensive unit tests for the multi-tenancy subsystem: TenantAwareAdapterMixin, TenantMiddleware, and tenant configuration.

## Acceptance Criteria

- [ ] Test TenantAwareAdapterMixin list filtering by tenant_id
- [ ] Test TenantAwareAdapterMixin create auto-assigns tenant_id
- [ ] Test TenantAwareAdapterMixin get scoping
- [ ] Test TenantMiddleware user profile resolution
- [ ] Test TenantMiddleware header resolution
- [ ] Test TenantMiddleware 400 on missing tenant
- [ ] Test AdminOptions tenant_field config
- [ ] Test HyperAdminSettings tenant_enabled/tenant_header
- [ ] Near 99% coverage for tenant-related code

## Files Likely Affected
- `tests/unit/test_tenant_adapter.py` (new)
- `tests/unit/test_auth_middleware.py` (extend)
- `tests/unit/test_settings.py` (extend)

## Dependencies
Depends on: #449 (TenantMiddleware), #450 (tenant config)

## Notes for Implementer
- Use mock objects for request.state.tenant_id
- Test that non-tenant models are unaffected
