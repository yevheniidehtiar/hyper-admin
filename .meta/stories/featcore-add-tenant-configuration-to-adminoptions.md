---
type: story
id: 1JmK6STiUpqa
title: "feat(core): add tenant configuration to AdminOptions"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
  - area:settings
estimate: null
epic_ref: null
github:
  issue_number: 450
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3ea971839c4c95037c64d975f68d5ce50ddbd487f3584ad0bb39f3f03fde56d6
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:42:49Z
updated_at: 2026-04-01T21:42:49Z
---

## Context

Users need to configure which field on their models represents the tenant and whether tenant filtering is enabled globally.

## Scenarios

**Scenario: AdminOptions with tenant_field configures tenant filtering**
  Given `AdminOptions(tenant_field="organization_id")`
  When  the options are inspected
  Then  `tenant_field` is "organization_id"

**Scenario: tenant_field defaults to None (no tenant filtering)**
  Given `AdminOptions()` with no `tenant_field`
  When  the options are inspected
  Then  `tenant_field` is None

## Acceptance Criteria

- [ ] `tenant_field: str | None = None` added to `AdminOptions`
- [ ] `tenant_enabled: bool = False` added to `HyperAdminSettings`
- [ ] `tenant_header: str = "X-Tenant-ID"` added to `HyperAdminSettings`
- [ ] Unit tests cover both scenarios
- [ ] Existing tests pass

## Files Likely Affected
- `src/hyperadmin/core/options.py`
- `src/hyperadmin/core/settings.py`
- `tests/unit/test_settings.py`

## Dependencies
Depends on: #448 (TenantAwareAdapterMixin — design must be stable)

## Notes for Implementer
- `tenant_field` is per-model (AdminOptions), `tenant_enabled` is global (Settings)
- When `tenant_enabled=False`, TenantMiddleware should not be registered
