---
type: story
id: fvB1i7v9QqNL
title: "docs(spec): SDD for object permissions & MFA"
status: todo
priority: medium
assignee: null
labels:
  - documentation
  - size:S
  - planned
  - auth
estimate: null
epic_ref:
  id: ufsAiAiHcy3m
github:
  issue_number: 474
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:266178419d0e25f176cc6ea4688865a2a890690d23b27990def4c9f56690b000
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-02T13:49:54Z
updated_at: 2026-04-02T13:49:54Z
---

## Summary

Write the Software Design Document for the Object-Level Permissions & MVP OTP/MFA epic (#473).

**Output:** `docs/specs/object-permissions-mfa.md`

## Scope

The SDD must cover:
- ObjectPermission protocol design (method signatures, superuser bypass)
- `get_queryset()` hook design (BaseAdapter, SQLModelAdapter, ModelAdmin)
- View-layer integration (how list/detail/update/delete use the hooks)
- User model MFA fields (`mfa_enabled`, `mfa_method`)
- EmailOTPService design (code generation, storage, expiry, verification)
- MFA challenge flow (session state management between password + OTP steps)
- Edge cases: expired codes, rate limiting, fallback when email fails

## Acceptance Criteria

- [ ] SDD follows `docs/specs/TEMPLATE.md` structure
- [ ] BDD scenarios synced with epic body
- [ ] Status set to "Draft"
- [ ] All 4 affected modules documented (auth/, core/, adapters/, views/)

## Parent

- Epic: #473
