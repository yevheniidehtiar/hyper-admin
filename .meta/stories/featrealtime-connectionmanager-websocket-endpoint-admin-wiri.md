---
type: story
id: gBxIBROQg18f
title: "feat(realtime): ConnectionManager + WebSocket endpoint + Admin wiring"
status: todo
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:L
  - area:realtime
estimate: null
epic_ref: null
github:
  issue_number: 307
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c3564318c11b52c10a22a8664f9b423a5d4ac924e0c10196f42b3548f045e1b2
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T06:58:29Z
updated_at: 2026-03-29T06:58:29Z
---

## Context
Core infrastructure task. Implements the WebSocket endpoint that browsers connect to, the ConnectionManager that routes messages, and wires pubsub_backend into the Admin class. All subsequent real-time features (notifications, presence) depend on this.

## Acceptance Criteria
- [ ] `src/hyperadmin/views/websocket.py` created with `ConnectionManager` class
- [ ] `GET /ws` WebSocket route added in `routing.py` (query param: `?channel=model:list` or `model:pk`)
- [ ] `pubsub_backend` kwarg added to `Admin.__init__()` with default `InMemoryPubSub()`
- [ ] `htmx-ws.js` (HTMX WebSocket extension) added to `src/hyperadmin/static/js/`
- [ ] All T5 tests pass
- [ ] Backward compatible: existing Admin instantiation without `pubsub_backend` works unchanged

## Files Likely Affected
- `src/hyperadmin/views/websocket.py` (new)
- `src/hyperadmin/routing.py`
- `src/hyperadmin/core/app.py`
- `src/hyperadmin/static/js/htmx-ws.js` (new, vendored)

## Dependencies
Depends on: #306

## Notes for Implementer
This is a `size:L` task — architectural. Follow CONSTITUTION.md dependency direction strictly: `views/websocket.py` imports from `core/realtime.py`, never the reverse. The WS endpoint authenticates via existing session middleware (no separate auth needed). Channel key format: `{model_name}:list` for list views, `{model_name}:{pk}` for record views.
