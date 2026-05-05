---
type: story
title: "feat(realtime): WebSocket endpoint + ping/pong + auth gate + Admin wiring"
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
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Context
Adds a bidirectional WebSocket endpoint at `WS {admin_prefix}/realtime/ws`. Zero business payload in the MVP — only ping/pong frames — but the endpoint must enroll with `ConnectionRegistry`, enforce session auth at the handshake, and unwind cleanly on close. PubSub fan-out is added later (after #303 merges) with a small follow-up.

## Scenarios

**Scenario: authenticated handshake succeeds**
  Given an authenticated session cookie
  When  the client opens `new WebSocket('ws://.../admin/realtime/ws')`
  Then  the handshake completes with status `101`
  And   `ConnectionRegistry.count()` is `≥ 1`

**Scenario: unauthenticated handshake is closed with 4401**
  Given no valid session cookie
  When  the client opens the WebSocket
  Then  the server accepts then immediately closes with code `4401`
  And   no entry is added to `ConnectionRegistry`

**Scenario: ping/pong keeps the connection alive**
  Given an open authenticated WebSocket
  When  N×heartbeat-interval elapses with no client send
  Then  the connection remains open
  And   server-side ping frames are observed at the configured interval

**Scenario: client disconnect unregisters the connection**
  Given an open WebSocket
  When  the client calls `ws.close()`
  Then  the server handler returns
  And   `ConnectionRegistry.count()` drops by 1

**Scenario: server shutdown closes the socket with 1001**
  Given an open WebSocket
  When  the server lifespan shuts down
  Then  the client observes a close with code `1001` (going away)
  And   no `RuntimeError` is logged server-side

## Acceptance Criteria
- [ ] `src/hyperadmin/realtime/ws.py` created with the WS handler
- [ ] Route registered in `Admin.mount()` via `self.app.add_websocket_route(...)` at path `{admin_prefix}/realtime/ws`
- [ ] Auth gate runs **inside** the handler (BaseHTTPMiddleware does not cover WS scope) — call `auth_backend.get_current_user(websocket)` after `await websocket.accept()`, close with code `4401` if `None`
- [ ] Heartbeat task uses `asyncio.create_task` with `asyncio.shield` and is cancelled on disconnect
- [ ] Connection enrolled with `ConnectionRegistry` for the duration
- [ ] No business payload in MVP — only protocol-level ping/pong

## Files Likely Affected
- `src/hyperadmin/realtime/ws.py` (new)
- `src/hyperadmin/realtime/__init__.py` (extend exports)
- `src/hyperadmin/core/app.py` — `Admin.mount()` (register WS route)

## Dependencies
Spec: `docs/specs/realtime-connection-foundation.md`
Blocked by: ConnectionRegistry implementation
Can run in parallel with: SSE endpoint story
