---
type: epic
id: 41R3nX0XoedV
title: "epic(adapters): Multi-Tenancy Filtering"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:auth
  - area:adapters
  - roadmap
milestone_ref: null
github:
  issue_number: 421
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:511434318b77ba83fb4a4116c0b0d556468131b3bc0f4dfe3d7d06e6437a7bd6
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:36:04Z
updated_at: 2026-04-01T21:46:37Z
---

## Overview

Implement multi-tenancy filtering using the `get_queryset()` hook from Epic #419.

**Milestone**: v0.5.3 — Multi-Tenancy  
**SDD Required**: No (all S/M issues building on existing get_queryset hook)  
**Modules affected**: adapters/, auth/, core/  
**Depends on**: Epic #419 issues #426 + #427 + #428 (get_queryset hook must be wired)

### What's included

- `TenantAwareAdapterMixin` — filters all queries by `tenant_id`
- `TenantMiddleware` — resolves tenant from user profile, header, or subdomain
- Tenant configuration in AdminOptions (`tenant_field`) and HyperAdminSettings (`tenant_enabled`)
- Unit + E2E tests for tenant isolation
- Documentation: multi-tenant usage patterns

### Dependency DAG

```
[Epic 1: #428] → #448 ──┬──► #449 ──┐
                         └──► #450 ──┼──► #451 → #453 → #454
                                     └───────────┘
```

## Tasks
- [ ] #448 — feat(adapters): create TenantAwareAdapter mixin
- [ ] #449 — feat(auth): create TenantMiddleware for tenant resolution
- [ ] #450 — feat(core): add tenant configuration to AdminOptions
- [ ] #451 — test: unit tests for multi-tenant filtering
- [ ] #453 — test(e2e): multi-tenant list isolation
- [ ] #454 — docs: multi-tenant usage patterns
