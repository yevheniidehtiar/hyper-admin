---
type: story
id: U2-raDoexJC8
title: "chore(examples): restructure examples/ — move simple app, delete rbac_app"
status: done
priority: medium
assignee: null
labels:
  - in-progress
  - jules
  - agent-task
  - area:examples
  - size:S
estimate: null
epic_ref:
  id: w5uOHybW-qhx
github:
  issue_number: 191
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:62d924bdf2349c99bac5eba4424308b6b59ee4764d2acbc32f7569f60ab6fa62
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-25T13:41:09Z
updated_at: 2026-03-25T15:23:57Z
---

> **Part of:** #172
> **No dependencies (base task)**

## Acceptance Criteria
- [ ] `examples/rbac_app/` deleted
- [ ] `examples/simple/` created with existing simple app files moved in
- [ ] Existing simple example still runs: `uv run uvicorn examples/simple/main:app`
- [ ] No ruff/mypy errors

## Files
- `examples/` (restructure)

