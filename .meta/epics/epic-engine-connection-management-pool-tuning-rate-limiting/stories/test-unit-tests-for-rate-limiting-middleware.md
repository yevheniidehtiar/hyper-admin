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
- [ ] Requests over the per-client limit get HTTP 429 with `Retry-After`, and the app is not called
- [ ] Limits are per client address; a missing client counts as one `unknown` client
- [ ] Configurable limits and window; refill over time; no banking beyond the limit
- [ ] Static assets, websocket scopes and host routes outside the admin prefix bypass the limit
- [ ] The limiter is pluggable: a custom protocol implementation passed as `Admin(rate_limiter=...)` replaces the in-memory one
- [ ] The login limit counts only login POSTs, and either limit can deny them
- [ ] A single global bucket is intentionally not built: it would let one client lock everyone out (corrected from "global rate limit enforcement")

## Files
- `tests/unit/test_rate_limit.py` (new)

## Dependencies
- Blocked by: none
- Blocking: #234
