---
type: story
id: GHy3YZTKE9I2
title: "test(realtime): PubSubBackend protocol + InMemoryPubSub unit tests"
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
  issue_number: 302
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:a63b3d4878e464079e2dfd57d607032db609c32d6a6023bad1862551cf0e3e6a
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:57:43Z
updated_at: 2026-03-29T06:57:43Z
---

## Context
Foundation for all real-time features. PubSubBackend is the protocol all pub/sub implementations must satisfy. InMemoryPubSub is the zero-config default for single-process deployments.

## Acceptance Criteria
- [ ] Failing tests for publish/subscribe/unsubscribe on InMemoryPubSub
- [ ] Test: multiple concurrent subscribers on same channel each receive the message
- [ ] Test: channel isolation — message on ch-A does not reach ch-B subscriber
- [ ] Test: cleanup on unsubscribe (no memory leak)
- [ ] All tests are written in `tests/unit/test_pubsub_memory.py`

## Files Likely Affected
- `tests/unit/test_pubsub_memory.py` (new)

## Dependencies
None — first task in Track A.

## Notes for Implementer
Follow existing test patterns in `tests/unit/`. Use `pytest-asyncio` for async tests. Tests must FAIL before implementation (TDD).
