---
type: milestone
id: XnHVJphQRoMf
title: v0.8.0 — Plugins & AI
target_date: 2026-10-30T00:00:00Z
status: in_progress
github:
  milestone_id: 18
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:38e5d6cb0f66885c2caf2342bda847f266131f0d82b1fce6272005c0481244c2
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2026-03-29T09:35:06Z
updated_at: 2026-03-29T09:35:06Z
---

Re-themed for v0.8.0: ship the **Plugin Registry + lifecycle hooks** (`hyperadmin.plugins`
entry points) and the first official plugin **hyperadmin-logfire** as proof-of-concept.
AI-assisted features (RFC #277), additional ORM adapters (Tortoise / Piccolo / MongoDB),
and custom non-CRUD page registration deferred to v0.8.1+.

Epics:
- `epic-plugins-registry-and-lifecycle-hooks` (size:L, SDD: `docs/specs/plugin-registry.md`)
- `epic-plugin-logfire-first-plugin` (size:L, SDD: `docs/specs/plugin-logfire.md`, blocked by Epic 1)
