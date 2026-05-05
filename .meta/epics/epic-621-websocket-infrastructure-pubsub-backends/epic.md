---
type: epic
id: MxA3yEbHFb9t
title: "Epic 6.2.1: WebSocket Infrastructure & PubSub Backends"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:realtime
milestone_ref:
  id: EnCx0HBhFy40
github:
  issue_number: 330
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0f986f1a5da15205ca3e94daccc4678d5dcb2c88b130e8283c56fff4d2cb0d97
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:02:09Z
updated_at: 2026-03-29T07:02:10Z
---

## Overview
Establishes the real-time foundation in two layers:

1. **MVP connection foundation** — SSE + WebSocket endpoints with zero business logic. Both transports are lifecycle-correct (connect, disconnect, reconnect after refresh / server restart) and gated by the existing session auth. A `ConnectionRegistry` tracks active connections for observability and shutdown drain. No PubSub. No fan-out.
2. **PubSub layer** — `PubSubBackend` protocol with `InMemoryPubSub` (zero-config) and `RedisPubSub` (multi-worker), wired into the WS endpoint after the MVP lands so subsequent features (CRUD events in 6.2.2, presence in 6.2.4) can broadcast.

The MVP slice can ship before the PubSub stories complete; the PubSub follow-up plugs `pubsub_backend.subscribe(...)` into the existing WS handler with a small diff.

## Roadmap Reference
Epic 6.2.1 — WebSocket Infrastructure & PubSub Backends

## Milestone
v0.6.0

## Tasks

### MVP slice (connection foundation, ships first)
- [ ] docs(spec): SDD for real-time connection foundation
- [ ] test(realtime): ConnectionRegistry unit tests (#306, rewritten)
- [ ] feat(realtime): ConnectionRegistry implementation
- [ ] feat(realtime): SSE endpoint + heartbeat + auth gate + Admin wiring
- [ ] feat(realtime): WebSocket endpoint + ping/pong + auth gate + Admin wiring
- [ ] feat(realtime): connection-status JS widget in _base.html (auto-reconnect + backoff)
- [ ] test(e2e): real-time connection lifecycle (connect / navigate / refresh / restart / auth / drain)

### PubSub layer (parallel; plugs into MVP afterwards)
- [ ] #302 — test(realtime): PubSubBackend protocol + InMemoryPubSub unit tests
- [ ] #303 — feat(realtime): PubSubBackend protocol + InMemoryPubSub implementation
- [ ] #304 — test(realtime): RedisPubSub unit tests (mocked aioredis)
- [ ] #305 — feat(realtime): RedisPubSub implementation + [redis] optional extra

The original #307 story (`feat(realtime): ConnectionManager + WebSocket endpoint + Admin wiring`) has been replaced by the four MVP `feat`/`test(e2e)` stories above; it carried both the connection layer and the PubSub fan-out, which we now ship in two reviewable steps.

## Parallel Tracks
The MVP slice runs sequentially (SDD → registry tests → registry impl → SSE + WS in parallel → widget → E2E). PubSub stories T1→T2→T3→T4 run independently and merge after the MVP. A short follow-up wires `pubsub_backend.subscribe(...)` into `realtime/ws.py` once both tracks land.
