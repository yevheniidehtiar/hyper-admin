---
type: epic
id: Y-nzspSqDFUM
title: "Epic 6.2.4: Presence Tracking — Who Is Editing What"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:presence
milestone_ref:
  id: 1U5Neu25VVR2
github:
  issue_number: 333
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f730517c0390ff399a54fbc1b72498f10a9734813d4c8dd868346ea7d16dc6a9
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:02:37Z
updated_at: 2026-03-29T07:02:37Z
---

## Overview
Shows which admins are currently viewing or editing the same record, preventing duplicate work. Builds on top of the WebSocket ConnectionManager from Epic 6.2.1. Ships InMemoryPresence (default) and RedisPresence (multi-worker).

## Roadmap Reference
Epic 6.2.4 — Presence Tracking — Who Is Editing What

## Milestone
v0.6.3

## Tasks
- [ ] #322 — test(presence): PresenceBackend protocol + InMemoryPresence unit tests
- [ ] #323 — feat(presence): PresenceBackend protocol + InMemoryPresence implementation
- [ ] #324 — test(presence): RedisPresence unit tests (mocked aioredis)
- [ ] #325 — feat(presence): RedisPresence implementation
- [ ] #326 — test(presence): Presence heartbeat WebSocket message handling
- [ ] #327 — feat(presence): Heartbeat handler + presence broadcasts in ConnectionManager
- [ ] #328 — feat(presence): presence_banner.html + update.html integration
- [ ] #329 — test(e2e): Presence banner — two sessions editing same record

## Parallel Tracks
P1→P4 (PresenceBackend + Redis track) can be developed in parallel with v0.6.2. P5 requires T6 (#307) from v0.6.2 to be merged first.
