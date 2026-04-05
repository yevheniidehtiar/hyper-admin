---
type: story
id: 8A7FYoycCl4n
title: "docs: multi-tenant usage patterns"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - agent-task
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 454
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:43953057d283017c70ad84ab822a3af2a194cfaac91a548e699131d10235fff5
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-01T21:43:20Z
updated_at: 2026-04-01T21:43:20Z
---

## Context

Developers need documentation on how to set up multi-tenancy with HyperAdmin. This guide covers the TenantAwareAdapterMixin, TenantMiddleware configuration, and common patterns.

## Acceptance Criteria

- [ ] Guide at `docs/guides/multi-tenancy.md`
- [ ] Overview of multi-tenancy approach (query-level filtering vs schema-level)
- [ ] Step-by-step setup: model with tenant_id, adapter mixin, middleware, settings
- [ ] Example code: custom ModelAdmin with tenant-scoped get_queryset
- [ ] Example code: TenantAwareAdapterMixin usage
- [ ] Explanation of header-based vs user-profile-based tenant resolution
- [ ] Security considerations (never trust client-provided tenant_id alone)

## Files Likely Affected
- `docs/guides/multi-tenancy.md` (new)

## Dependencies
Depends on: #452 (E2E tests passing — confirms feature works)

## Notes for Implementer
- Follow existing guide format in `docs/guides/file-uploads.md`
- Include a complete working example
