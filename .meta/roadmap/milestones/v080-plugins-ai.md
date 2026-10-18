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
updated_at: 2026-10-18T00:00:00Z
---

**Roadmap position 15/16 (2026-09-28 re-cut).** Plugin registry + lifecycle hooks and the first official plugin (hyperadmin-logfire); AI-assisted features after.

Re-themed for v0.8.0: ship the **Plugin Registry + lifecycle hooks** (`hyperadmin.plugins`
entry points) and the first official plugin **hyperadmin-logfire** as proof-of-concept.
AI-assisted features (RFC #277), additional ORM adapters (Tortoise / Piccolo / MongoDB),
and custom non-CRUD page registration deferred to v0.8.1+.

Epics:
- `epic-plugins-registry-and-lifecycle-hooks` (size:L, SDD: `docs/specs/plugin-registry.md`)
- `epic-plugin-logfire-first-plugin` (size:L, SDD: `docs/specs/plugin-logfire.md`, blocked by Epic 1)

**Roadmap change (2026-10-18).** The plugin registry is pulled forward ahead of v0.8.0: OLAP
reporting and the SVG charts become the first-party plugin **`hyperadmin-reports`**
(`plugins/hyperadmin-reports/`, own PyPI distribution), so phase 1 of
`epic-plugins-registry-and-lifecycle-hooks` (registry + UI extension seams: pages, nav,
templates, static, permissions, typed settings) lands before v0.8.0. What stays in v0.8.0:
firing CRUD / adapter lifecycle hooks from core (phase 2), `hyperadmin plugins list`, and
**`hyperadmin-logfire` as the second plugin**. SDD: `docs/specs/plugin-registry.md` ("Phasing").
