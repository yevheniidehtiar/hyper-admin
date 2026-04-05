---
type: story
id: mkTy4Fj-oiao
title: "docs: update examples to use HyperAdminSettings"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:examples
  - area:docs
  - size:S
estimate: null
epic_ref: null
github:
  issue_number: 380
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3ec647aed2021a20b9a355a07e692672017e6fbc5831f7e1cde4a98a3e2fe75a
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-31T09:09:57Z
updated_at: 2026-03-31T19:59:06Z
---

## Context

Update `examples/erp/` and `examples/simple/` to use `HyperAdminSettings` instead of passing scalar params directly to `Admin()`. Demonstrates the new Django-like configuration pattern.

## Acceptance criteria

- [ ] `examples/erp/main.py` uses `HyperAdminSettings` for config
- [ ] `examples/simple/main.py` uses `HyperAdminSettings` for config
- [ ] Remove hardcoded `session_secret="super-secret-erp-key"` from examples
- [ ] Show `.env` file usage in example README or comments
- [ ] Examples still work with `poe test:e2e`

## Files likely affected

- `examples/erp/main.py`
- `examples/simple/main.py`
- `examples/erp/.env.example` (new, optional)

## Dependencies

Depends on: #376
