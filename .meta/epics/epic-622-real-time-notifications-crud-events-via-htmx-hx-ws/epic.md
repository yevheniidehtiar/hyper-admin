---
type: epic
id: s7b6Ksi2ENu4
title: "Epic 6.2.2: Real-Time Notifications (CRUD Events via HTMX hx-ws)"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:realtime
milestone_ref:
  id: EnCx0HBhFy40
github:
  issue_number: 331
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5e2a28b5ccf936398c4f8287e0e593ca3b2f315188cd24d915abc1ccb601e9ad
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:02:19Z
updated_at: 2026-03-29T07:02:19Z
---

## Overview
Delivers live CRUD notifications to all connected browsers: RealtimeEvent types, adapter event emission, toast component, and out-of-band HTMX row swaps. Depends on Epic 6.2.1 being merged.

## Roadmap Reference
Epic 6.2.2 — Real-Time Notifications (CRUD Events via HTMX hx-ws)

## Milestone
v0.6.2

## Tasks
- [ ] #308 — test(realtime): RealtimeEvent dataclass unit tests
- [ ] #309 — feat(realtime): RealtimeEvent types in core/realtime.py
- [ ] #310 — test(realtime): CRUD event emission from adapters
- [ ] #311 — feat(realtime): Emit RealtimeEvents from SQLModelAdapter + SQLAlchemyAdapter
- [ ] #312 — feat(realtime): Toast component + hx-ws integration in list templates
- [ ] #313 — test(e2e): Live notifications — two browser sessions on same list view

## Parallel Tracks
T7→T8→T9→T10 (event types + adapter track) runs before T11 (template assembly). T12 (E2E) is last.
