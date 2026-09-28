---
type: story
id: st-v058-byoa-42
title: "feat(realtime): hashable user keys, bridge-aware SSE/WS and WebSocket Origin check"
status: todo
priority: high
assignee: null
labels:
  - size:S
  - planned
  - area:realtime
  - layer:views
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Widen `RealtimeConnection.user_id` to `Hashable`, and make `_debug.py` sort with `key=str`. SSE and WebSocket read `request.state.user_key`, which `AuthenticationMiddleware` now also sets. The WebSocket route is registered in bridge mode only when `websocket_user` is set, and the WebSocket handshake checks `Origin`.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — section: B (realtime), Reconciliation

## Files to Change

- `src/hyperadmin/realtime/registry.py`
- `src/hyperadmin/realtime/sse.py`
- `src/hyperadmin/realtime/ws.py`
- `src/hyperadmin/realtime/_debug.py`
- `src/hyperadmin/auth/middleware.py`
- `src/hyperadmin/core/app.py`
- `tests/unit/test_realtime_bridge.py`

## Scenarios

```
Scenario: UUID principal
  Given realtime enabled and a bridged user with a UUID id
  When  GET /admin/realtime/sse is requested
  Then  a connection is registered under that UUID key

Scenario: mixed key types
  Given connections for int and UUID users
  When  the debug snapshot is built
  Then  it does not raise

Scenario: foreign-origin WS closed
  Given realtime with built-in auth
  When  a WS handshake arrives with Origin: https://evil.example
  Then  the socket is closed with the unauthorized code

Scenario: bridge without websocket_user
  Given bridge mode and no websocket_user
  When  the admin mounts
  Then  no WS route is registered
```

## Acceptance Criteria

- [ ] UUID principal
- [ ] mixed key types
- [ ] foreign-origin WS closed
- [ ] bridge without websocket_user
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featcore-adminauth-externalauth-wiring-and-opt-in-built-in-a` (st-v058-byoa-40)

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
