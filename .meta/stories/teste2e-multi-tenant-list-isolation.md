---
type: story
id: jkO1g6efwRLF
title: "test(e2e): multi-tenant list isolation"
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
  issue_number: 453
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:4b6eb40054bc21f67ac6cf0b6df288e3daa0add5cc1c0b1b7254e92924d72fff
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:43:18Z
updated_at: 2026-04-01T21:43:18Z
---

## Context

E2E Playwright tests verifying tenant data isolation through the full stack.

## Scenarios

**Scenario: tenant A sees only their records in list view**
  Given tenant A has 3 records, tenant B has 5 records
  When  user from tenant A views the list
  Then  only 3 records are displayed

**Scenario: tenant A cannot access tenant B's record via detail URL**
  Given record #10 belongs to tenant B
  When  user from tenant A navigates to `/admin/model/10`
  Then  a 404 is returned (record not found for this tenant)

**Scenario: creating a record auto-assigns current tenant_id**
  Given user from tenant A creates a new record
  When  the record is saved
  Then  `tenant_id` is automatically set to tenant A's ID

## Acceptance Criteria

- [ ] E2E test app with tenant-aware model and two tenants
- [ ] All 3 scenarios pass as Playwright tests
- [ ] Inline `# Given / # When / # Then` comments
- [ ] Accessibility-first selectors

## Files Likely Affected
- `tests/e2e/test_multi_tenancy.py` (new)
- `tests/e2e/conftest.py`

## Dependencies
Depends on: #451 (unit tests passing)

## Notes for Implementer
- Need a test model with `tenant_id` field
- Two test users with different `tenant_id` values
- Use `TenantAwareAdapterMixin` + `TenantMiddleware` in the test app
