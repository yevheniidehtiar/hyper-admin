---
type: story
id: xFDbO4WWuQv5
title: "feat(core): rate limiter protocol and in-memory implementation"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:core
  - agent:claude
  - size:M
  - performance
estimate: null
epic_ref:
  id: ed1DCvpnaZ1w
github:
  issue_number: 234
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7994fe46476faffca0fa15046b1ab4703e959943bef9d4bd38024b133e04be8c
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:42:16Z
updated_at: 2026-03-27T00:42:16Z
---

## Context
Part of Epic #212 (B2: Rate limiting middleware).

## Acceptance criteria
- [ ] `RateLimiter` protocol defined in `core/rate_limit.py` with `is_allowed(key: str) -> bool` and `record_request(key: str) -> None`
- [ ] `InMemoryRateLimiter` implementation using token-bucket algorithm
- [ ] Configurable: `requests_per_window: int`, `window_seconds: int`
- [ ] Thread-safe (async-compatible)
- [ ] Pluggable: Redis backend can be added later without changing protocol
- [ ] All tests from B2.1 pass

## Files
- `src/hyperadmin/core/rate_limit.py` (new)

## Dependencies
- Blocked by: #233 (B2.1 tests)
- Blocking: B2.3
