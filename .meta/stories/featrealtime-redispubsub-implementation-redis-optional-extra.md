---
type: story
id: v4wIz4uDwDKp
title: "feat(realtime): RedisPubSub implementation + [redis] optional extra"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 305
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:03d534f3e7c577ab75013d6d23e8a62dad13c7eef73e2a536d91a07abbcd9355
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:10Z
updated_at: 2026-03-29T06:58:10Z
---

## Context
Production-grade PubSub backend for multi-worker deployments. Ships as optional extra to keep the core dependency footprint minimal.

## Acceptance Criteria
- [ ] `src/hyperadmin/adapters/pubsub/redis.py` created implementing `PubSubBackend`
- [ ] `redis[hiredis]>=5.0` added to `pyproject.toml` `[project.optional-dependencies]` under `[redis]` key
- [ ] `aioredis` or `redis.asyncio` used for async operations
- [ ] All tests from T3 pass
- [ ] Import guard: `ImportError` with helpful message if `redis` not installed

## Files Likely Affected
- `src/hyperadmin/adapters/pubsub/redis.py` (new)
- `pyproject.toml`

## Dependencies
Depends on: #304

## Notes for Implementer
Use `redis.asyncio` (bundled with `redis` package ≥4.2) rather than the deprecated `aioredis` package. Wrap import in try/except ImportError.
