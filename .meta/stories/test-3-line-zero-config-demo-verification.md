---
type: story
id: x-b2D_RiGBNd
title: "test: 3-line zero-config demo verification"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 372
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:903b895160b3e022585c9dfb016f1878dd0e8081709bf8ed68b06219938bb5a3
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:59:34Z
updated_at: 2026-03-31T20:43:37Z
---

## Context

Verify the minimal zero-config setup works: `admin = Admin(app, engine=engine); admin.mount("/admin")` with CRUD for auto-discovered models.

## Scenarios

**Scenario: 3-line setup produces working admin**
  Given a FastAPI app with 2 SQLModel table models and an engine
  When  `Admin(app, engine=engine).mount("/admin")` is called with no other config
  Then  both models appear in the admin
  And   list, create, detail, edit, delete views are functional

## Acceptance criteria

- [ ] Integration test demonstrating 3-line setup
- [ ] Verify all 5 CRUD views are generated for each auto-discovered model
- [ ] Test passes with zero explicit `site.register()` calls

## Files likely affected

- `tests/unit/test_zero_config.py` (new) or extend existing integration tests

## Dependencies

Depends on: #370, #371
