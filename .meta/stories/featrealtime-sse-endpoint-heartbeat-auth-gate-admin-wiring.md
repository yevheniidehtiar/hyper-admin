---
type: story
title: "feat(realtime): SSE endpoint + heartbeat + auth gate + Admin wiring"
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
Adds a one-way Server-Sent Events endpoint at `GET {admin_prefix}/realtime/sse`. Zero business payload — only periodic heartbeat comments — but the endpoint must register with `ConnectionRegistry`, respect the existing session auth, and shut down cleanly when the client goes away or the server stops.

## Scenarios

**Scenario: authenticated client receives heartbeats**
  Given an authenticated session
  When  the client opens `EventSource('/admin/realtime/sse')`
  Then  the response status is `200`
  And   `Content-Type` is `text/event-stream`
  And   the client receives at least one `:keepalive` comment within 2× heartbeat-interval

**Scenario: unauthenticated request is rejected**
  Given no valid session cookie
  When  the client GETs `/admin/realtime/sse`
  Then  the response is `401`
  And   `Content-Type` is NOT `text/event-stream`

**Scenario: client disconnect unregisters the connection**
  Given an open SSE stream
  When  the client closes the connection
  Then  `ConnectionRegistry.count()` drops by 1 within 2 s
  And   the heartbeat coroutine is cancelled (no leaked task)

**Scenario: server shutdown closes the stream cleanly**
  Given an open SSE stream
  When  the server lifespan shuts down
  Then  the response generator exits without raising
  And   no warning is logged

## Acceptance Criteria
- [ ] `src/hyperadmin/realtime/sse.py` created with the SSE handler
- [ ] Route registered in `Admin.mount()` via `self.router.add_api_route(...)` at path `/realtime/sse`
- [ ] Endpoint uses `starlette.responses.StreamingResponse` (no new dep)
- [ ] Heartbeat interval comes from `RealtimeSettings.heartbeat_interval` (default 15 s)
- [ ] Auth gate: `request.state.user` checked; `401` when missing
- [ ] Connection enrolled with `ConnectionRegistry` for the duration of the stream
- [ ] Inline `# Given / # When / # Then` comments in any unit-level coverage
- [ ] No business payload — only `:keepalive` comments

## Files Likely Affected
- `src/hyperadmin/realtime/config.py` (new)
- `src/hyperadmin/realtime/sse.py` (new)
- `src/hyperadmin/realtime/__init__.py` (extend exports)
- `src/hyperadmin/core/app.py` — `Admin.__init__` (add `realtime` kwarg) and `Admin.mount()` (register route)

## Dependencies
Spec: `docs/specs/realtime-connection-foundation.md`
Blocked by: ConnectionRegistry implementation
Can run in parallel with: WS endpoint story
