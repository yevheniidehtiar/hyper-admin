---
type: story
id: _voae0xmbjvw
title: "feat(core): engine factory accepting pool configuration"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - size:S
  - performance
estimate: null
epic_ref:
  id: fAZXHu4TtVlv
github:
  issue_number: 232
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:070104cf9112084a26a336b47199ac7a43b49b59cd7e0ae433052029dc2b1dba
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:42:09Z
updated_at: 2026-03-29T18:26:22Z
---

## Context
Part of Epic #212 (B1: Configurable engine kwargs).

## Acceptance criteria
- [ ] `db.py` refactored to accept `engine_kwargs: dict` param
- [ ] Production defaults documented: `pool_size=20, max_overflow=40, pool_timeout=30`
- [ ] SQLite detection skips pool kwargs automatically
- [ ] All tests from B1.1 pass

## Files
- `src/hyperadmin/db.py`

## Dependencies
- Blocked by: #231 (B1.1 tests)
- Blocking: none (standalone improvement)
