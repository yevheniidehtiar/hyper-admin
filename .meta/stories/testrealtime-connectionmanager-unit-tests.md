---
type: story
id: 72lX_h3zC2v-
title: "test(realtime): ConnectionRegistry unit tests"
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
  issue_number: 306
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b343de975604d4b412517561679b43fd441b92d1aea53a25bb98d396b0243594
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:18Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
The `ConnectionRegistry` is the only shared state for the real-time connection foundation. It tracks active SSE and WebSocket connections (count, per-user set) and exposes a drain hook used by the FastAPI lifespan to close every socket cleanly on shutdown. No PubSub, no fan-out — that lives in the PubSub stories (#302–#305) and is layered on afterwards.

Tests must FAIL before the implementation story lands.

## Scenarios

**Scenario: register increases count**
  Given an empty `ConnectionRegistry`
  When  a connection is registered for user `42`
  Then  `count()` returns `1`
  And   `users()` returns `{42}`

**Scenario: unregister decreases count**
  Given a registry with two connections for user `42`
  When  one connection is unregistered
  Then  `count()` returns `1`
  And   `42` is still in `users()`

**Scenario: unregistering the last connection for a user removes them**
  Given a registry with one connection for user `42`
  When  that connection is unregistered
  Then  `count()` returns `0`
  And   `users()` is empty

**Scenario: drain closes all connections**
  Given a registry with N connections (mix of SSE + WS)
  When  `drain()` is awaited
  Then  every connection's close hook is called exactly once
  And   `count()` returns `0` after drain

**Scenario: register after drain raises**
  Given a registry that has been drained
  When  a new connection is registered
  Then  a `RuntimeError` is raised (the registry is shut down)

**Scenario: concurrent register/unregister are safe**
  Given an empty registry
  When  100 concurrent register-then-unregister coroutines run
  Then  the final `count()` is `0`
  And   no exceptions are raised

## Acceptance Criteria
- [ ] Tests in `tests/unit/realtime/test_registry.py`
- [ ] One pytest function per scenario, named after the scenario title
- [ ] Each test has inline `# Given / # When / # Then` comments
- [ ] All tests fail until the impl story lands

## Files Likely Affected
- `tests/unit/realtime/__init__.py` (new)
- `tests/unit/realtime/test_registry.py` (new)

## Dependencies
Blocks: `feat(realtime): ConnectionRegistry implementation`

## Notes for Implementer
The connection objects in tests can be lightweight dataclasses with an async `close()` mock — no real SSE/WS needed. Use `pytest.mark.asyncio` and `asyncio.gather` for the concurrency scenario.
