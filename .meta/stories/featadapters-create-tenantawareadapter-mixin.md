---
type: story
id: O5dZ4y1Fr8-s
title: "feat(adapters): create TenantAwareAdapter mixin"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:adapters
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 448
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:95c80196ca701271726a8796d8d4f68a5696b66f7e75327a043ca11195aa1438
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:42:24Z
updated_at: 2026-04-01T21:42:24Z
---

## Context

Multi-tenancy requires automatic filtering of all database queries by `tenant_id`. This mixin overrides `get_queryset()` (from #426) to inject tenant filtering, and scopes `create()` to auto-assign `tenant_id`.

## Scenarios

**Scenario: TenantAwareAdapterMixin filters list by tenant_id**
  Given a model with `tenant_id` column
  And   `request.state.tenant_id = 42`
  When  `list()` is called through the mixin
  Then  only records with `tenant_id = 42` are returned

**Scenario: TenantAwareAdapterMixin scopes create to current tenant**
  Given `request.state.tenant_id = 42`
  When  `create(data)` is called
  Then  the new record has `tenant_id = 42` set automatically

**Scenario: TenantAwareAdapterMixin denies get() for wrong tenant**
  Given record #5 has `tenant_id = 99`
  And   `request.state.tenant_id = 42`
  When  `get(pk=5)` is called through the mixin
  Then  `None` is returned (as if record doesn't exist)

## Acceptance Criteria

- [ ] `TenantAwareAdapterMixin` class in `adapters/tenant.py` (new)
- [ ] Overrides `get_queryset()` to add `.where(Model.tenant_id == tenant_id)`
- [ ] Overrides `create()` to inject `tenant_id` into data
- [ ] Overrides `get()` to scope by tenant
- [ ] `tenant_id` extracted from `request.state.tenant_id`
- [ ] Configurable tenant field name (default: `tenant_id`)
- [ ] Unit tests cover all 3 scenarios

## Files Likely Affected
- `src/hyperadmin/adapters/tenant.py` (new)
- `tests/unit/test_tenant_adapter.py` (new)

## Dependencies
Depends on: #428 (get_queryset wired into views — Epic 1 OLP-6)

## Notes for Implementer
- This is a mixin, not a full adapter: `class TenantAwareAdapterMixin`
- Usage: `class TenantSQLModelAdapter(TenantAwareAdapterMixin, SQLModelAdapter): ...`
- The mixin reads `self.tenant_field` (str) to know which column to filter on
- CONSTITUTION.md: `adapters/` must not import from `views/`
