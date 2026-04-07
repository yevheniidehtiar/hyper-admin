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
Establishes the real-time foundation: PubSubBackend protocol, InMemoryPubSub (zero-config), RedisPubSub (multi-worker), ConnectionManager, and the WebSocket endpoint. All subsequent real-time features depend on this epic.

## Roadmap Reference
Epic 6.2.1 — WebSocket Infrastructure & PubSub Backends

## Milestone
v0.6.2

## Tasks
- [ ] #302 — test(realtime): PubSubBackend protocol + InMemoryPubSub unit tests
- [ ] #303 — feat(realtime): PubSubBackend protocol + InMemoryPubSub implementation
- [ ] #304 — test(realtime): RedisPubSub unit tests (mocked aioredis)
- [ ] #305 — feat(realtime): RedisPubSub implementation + [redis] optional extra
- [ ] #306 — test(realtime): ConnectionManager unit tests
- [ ] #307 — feat(realtime): ConnectionManager + WebSocket endpoint + Admin wiring

## Parallel Tracks
T1→T2→T3→T4 (PubSub track) and T5→T6 (ConnectionManager track) can be partially parallelized after T2 is complete.
