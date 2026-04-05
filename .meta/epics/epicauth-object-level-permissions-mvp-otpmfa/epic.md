---
type: epic
id: ufsAiAiHcy3m
title: "epic(auth): Object-Level Permissions & MVP OTP/MFA"
status: todo
priority: medium
owner: null
labels:
  - size:L
  - planned
  - auth
milestone_ref:
  id: wqxnL3QmE5lx
github:
  issue_number: 473
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f82c81897f60c02216ca7994268fc704936ca1910b49a481f1d6bcaba6d648cc
  synced_at: 2026-04-05T09:13:33.560Z
created_at: 2026-04-02T13:49:39Z
updated_at: 2026-04-02T13:49:39Z
---

## Overview

Introduce object-level permission checking and row-level security via `get_queryset()` hooks, plus MVP multi-factor authentication using email-based OTP codes.

**SDD:** `docs/specs/object-permissions-mfa.md` (required — touches auth/, core/, adapters/, views/)

## Tracks

### Track A: Object-Level Permissions & Row-Level Security
- `ObjectPermission` protocol in `core/auth.py`
- `object_permission_checker` field in `AdminOptions`
- `get_queryset()` hook in `BaseAdapter` + `SQLModelAdapter`
- `get_queryset()` hook in `ModelAdmin` base
- View-layer wiring: list_view filters by queryset, detail/update/delete check object permission

### Track B: MVP Email OTP/MFA
- `mfa_enabled`, `mfa_method` fields on User model
- `EmailOTPService` — generate, send, verify 6-digit codes
- MFA challenge view (enter code after password login)
- MFA enable/disable settings view
- Wire MFA into login flow (redirect to challenge if mfa_enabled)

## Acceptance Criteria

- [ ] Object permission protocol defined and wired
- [ ] `get_queryset()` filters list results per-user
- [ ] Detail/update/delete views enforce object-level checks
- [ ] Superuser bypasses all object-level restrictions
- [ ] Email OTP codes sent and verified during login
- [ ] MFA can be enabled/disabled per user
- [ ] Unit + E2E tests for both tracks
