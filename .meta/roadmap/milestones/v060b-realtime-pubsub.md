---
type: milestone
id: EnCx0HBhFy40
title: "v0.6.0b — Real-Time Pub/Sub & Live Notifications"
target_date: 2026-06-15T00:00:00Z
status: in_progress
github:
  milestone_id: 11
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d80bda4607ae2a00fe282edf834d163335eaafb15d58ad2d93c074820d43a235
  synced_at: 2026-04-07T17:23:23.788Z
created_at: 2026-03-29T06:57:27Z
updated_at: 2026-09-28T00:00:00Z
---

**Roadmap position 11/16 (2026-09-28 re-cut).** Connection foundation already shipped (SSE + WebSocket endpoints, `ConnectionRegistry`, status widget — PRs #551/#567). Remaining: `PubSubBackend` (InMemory + Redis), `RealtimeEvent` emission from adapters, live list updates via HTMX. Epics 6.2.1 (#330) and 6.2.2 (#331). OCC moved to v0.6.0a.

Original scope (before the 2026-09-28 split): Epic 6.2: WebSocket infrastructure, PubSub backends (InMemory + Redis), live CRUD notifications via HTMX hx-ws, Optimistic Concurrency Control with conflict dialog
