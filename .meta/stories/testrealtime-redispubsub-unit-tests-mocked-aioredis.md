---
type: story
id: TKeRz1E0Nw8B
title: "test(realtime): RedisPubSub unit tests (mocked aioredis)"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - size:S
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 304
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a3c31cf9ac14770d32f1bdfa27094662eeb227e94d0b046735288642384f45d3
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:01Z
updated_at: 2026-03-29T06:58:01Z
---

## Context
RedisPubSub enables multi-process deployments where multiple uvicorn workers need to share events. Tests use mocked aioredis to avoid requiring a live Redis instance in unit tests.

## Acceptance Criteria
- [ ] Failing tests for RedisPubSub using `pytest-mock` to mock aioredis
- [ ] Test: publish calls redis.publish on correct channel
- [ ] Test: subscribe yields messages from redis stream
- [ ] Test: unsubscribe cleans up redis subscription
- [ ] Test: connection errors propagate as exceptions
- [ ] Test: multiple channels handled independently
- [ ] Tests in `tests/unit/test_pubsub_redis.py`

## Files Likely Affected
- `tests/unit/test_pubsub_redis.py` (new)

## Dependencies
Depends on: #303

## Notes for Implementer
Tests must FAIL before T4 is implemented. Use `unittest.mock.AsyncMock` for async redis methods.
