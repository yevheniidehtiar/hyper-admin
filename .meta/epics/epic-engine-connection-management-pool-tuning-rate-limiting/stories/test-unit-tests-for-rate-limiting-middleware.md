---
type: story
id: uB0aWo6B3cwo
title: "test: unit tests for rate limiting middleware"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - agent:claude
  - size:M
  - area:middleware
  - performance
estimate: null
epic_ref:
  id: ed1DCvpnaZ1w
github:
  issue_number: 233
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:660add93d59982460deaedbbde0126d4789030136bbc96523ab2fe94964cdea1
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:12Z
updated_at: 2026-03-27T00:42:12Z
---

## Context
Part of Epic #212 (B2: Rate limiting middleware).
No rate limiting exists — 100 req/s spikes hit the DB directly.

## Acceptance criteria
- [ ] Test that requests exceeding per-IP limit get HTTP 429
- [ ] Test global rate limit enforcement
- [ ] Test configurable limits (requests per window)
- [ ] Test bypass for static asset paths
- [ ] Test that rate limiter is pluggable (protocol-based)

## Files
- `tests/unit/test_rate_limit_middleware.py` (new)

## Dependencies
- Blocked by: none
- Blocking: B2.2
