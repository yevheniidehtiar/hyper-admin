---
type: epic
id: 4E5yIMWxxB-N
title: "epic(auth): Wire Authentication End-to-End — Remaining Gaps"
status: done
priority: medium
owner: null
labels:
  - agent-task
  - area:auth
milestone_ref:
  id: WUIXeOSj83Kt
github:
  issue_number: 381
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:26a238169b23028737fb8f67dc9e50a655cd4cf90f91db165a0e26e088f4dbe7
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:11:17Z
updated_at: 2026-03-31T16:58:52Z
---

## Overview

Closes the last 2 gaps in the auth E2E stack. 5 of 7 original items are already implemented (SessionAuthBackend, middleware, login/logout views, PermissionChecker, createsuperuser CLI). Remaining: auto-registration of auth models and a Playwright E2E test.

## Tasks

- [ ] #361 — feat(auth): auto-register User/Group/Permission when auth_backend is set
- [ ] #362 — test(e2e): login → view protected model → logout flow

## Dependency Graph

```
#361 → #362
```

## Parallel Tracks

#361 must complete before #362 (E2E test depends on auto-registered auth models).
