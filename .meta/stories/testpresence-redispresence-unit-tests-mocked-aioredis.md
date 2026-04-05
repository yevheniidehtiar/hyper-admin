---
type: story
id: pX_8VhC3HkYX
title: "test(presence): RedisPresence unit tests (mocked aioredis)"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - area:presence
estimate: null
epic_ref: null
github:
  issue_number: 324
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cf5f593383c11ce53d00ee8f43648a81c58c2f74a7562bd071bde57def540cae
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-29T07:01:10Z
updated_at: 2026-03-29T07:01:10Z
---

## Context
RedisPresence enables presence tracking across multiple uvicorn workers.

## Acceptance Criteria
- [ ] Test: `set_presence` uses Redis HASH + EXPIRE for per-entry TTL
- [ ] Test: `get_presence` scans Redis keys by channel pattern and deserializes entries
- [ ] Test: `remove_presence` deletes the Redis key
- [ ] Test: expired keys not returned
- [ ] Tests use mocked `redis.asyncio` client
- [ ] Tests in `tests/unit/test_presence_redis.py`

## Files Likely Affected
- `tests/unit/test_presence_redis.py` (new)

## Dependencies
Depends on: #323

## Notes for Implementer
Tests must FAIL before P4.
