---
type: story
id: u2RHNQzG_c1M
title: "feat(core): add auto_discover parameter to Admin()"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - area:core
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 371
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f133e9376b9adf7f6df78db8f0d8a4a2b56ddf6a2b5b1e0a34cc5c854fcad0a7
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T08:59:02Z
updated_at: 2026-03-31T20:43:36Z
---

## Context

`auto_discover: bool = True` parameter on `Admin.__init__()`. When True, `_auto_register_models()` is called during `mount()`. When False, only explicit registrations used.

## Scenarios

**Scenario: auto_discover=True registers all models (default)**
  Given an app with 3 SQLModel table models and no explicit registrations
  When  `Admin(app, engine=engine).mount("/admin")` is called
  Then  all 3 models appear in `site._registry`

**Scenario: auto_discover=False skips discovery**
  Given an app with 3 SQLModel models
  When  `Admin(app, engine=engine, auto_discover=False).mount("/admin")` is called
  Then  `site._registry` contains only explicitly registered models

## Acceptance criteria

- [ ] `auto_discover: bool = True` parameter on `Admin.__init__()`
- [ ] `mount()` calls `_auto_register_models()` when `auto_discover=True`
- [ ] Backward compatible — existing apps default to auto-discovery on
- [ ] Unit tests for both True and False

## Files likely affected

- `src/hyperadmin/core/app.py`

## Dependencies

Depends on: #370
