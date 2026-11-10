---
type: story
id: xFDbO4WWuQv5
title: "feat(core): rate limiter protocol and in-memory implementation"
status: done
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
- [ ] `RateLimiter` protocol in `core/rate_limit.py` with one atomic `async acquire(key: str) -> RateLimitDecision` (`allowed`, `retry_after` seconds). Corrected from `is_allowed` plus `record_request`: a separate check and record lets concurrent requests all pass before any is counted, and the 429 needs a `Retry-After` value
- [ ] `InMemoryRateLimiter` using a token bucket: `requests_per_window` tokens refilled evenly over `window_seconds`, so a client may burst to the limit and then sustains the average rate
- [ ] Bounded memory: `max_keys` least-recently-seen buckets are kept
- [ ] Safe for concurrent tasks on one event loop (`acquire` never awaits)
- [ ] Pluggable: a shared (for example Redis) implementation of the protocol replaces it without changing the middleware. Counts are per process, which the docs state
- [ ] All tests from #233 pass

## Files
- `src/hyperadmin/core/rate_limit.py` (new)

## Dependencies
- Blocked by: #233
- Blocking: #235
