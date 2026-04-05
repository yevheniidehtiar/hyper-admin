---
type: story
id: crdqVzAjyqR6
title: "feat(presence): RedisPresence implementation"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:M
  - area:presence
estimate: null
epic_ref: null
github:
  issue_number: 325
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d804120bb15a7bd074e5a20ccc1b6686a5312fc7086462200061cfa222a30173
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:01:19Z
updated_at: 2026-03-29T07:01:19Z
---

## Context
Production-grade presence backend for multi-worker deployments. Reuses the `[redis]` optional extra from T4.

## Acceptance Criteria
- [ ] `src/hyperadmin/adapters/presence/redis.py` created implementing `PresenceBackend`
- [ ] Uses `redis.asyncio` (same dependency as RedisPubSub from T4)
- [ ] Per-entry TTL via Redis key expiry
- [ ] All P3 tests pass
- [ ] Import guard with helpful error if `redis` not installed

## Files Likely Affected
- `src/hyperadmin/adapters/presence/redis.py` (new)

## Dependencies
Depends on: #324

## Notes for Implementer
Key pattern: `presence:{channel}:{user_id}` with SETEX. `get_presence` uses SCAN with pattern `presence:{channel}:*`.
