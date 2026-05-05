---
type: story
title: "feat(realtime): ConnectionRegistry implementation"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:S
  - area:realtime
estimate: null
epic_ref: null
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
Implements the in-memory `ConnectionRegistry` to satisfy the unit tests in #306. Both transports (SSE, WS) call `register(...)` on connect and `unregister(...)` on disconnect; the FastAPI lifespan calls `drain()` on shutdown.

## Acceptance Criteria
- [ ] `src/hyperadmin/realtime/registry.py` created with `ConnectionRegistry` class
- [ ] Public methods: `register(conn)`, `unregister(conn)`, `count()`, `users()`, `drain()`
- [ ] All access paths protected by an `asyncio.Lock`
- [ ] After `drain()`, `register()` raises `RuntimeError`
- [ ] Re-exported from `src/hyperadmin/realtime/__init__.py`
- [ ] All tests in #306 pass
- [ ] Type-hinted; passes `poe lint`

## Files Likely Affected
- `src/hyperadmin/realtime/__init__.py` (new)
- `src/hyperadmin/realtime/registry.py` (new)

## Dependencies
Spec: `docs/specs/realtime-connection-foundation.md`
Blocked by: SDD approval, #306 tests merged
Blocks: SSE endpoint story, WS endpoint story
