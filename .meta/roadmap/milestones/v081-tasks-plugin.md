---
type: milestone
id: iOTodDwZehp2
title: v0.8.1 — Tasks plugin (pgtask, experimental)
target_date: 2026-11-13T00:00:00Z
status: in_progress
github:
  milestone_id: 23
  repo: yevheniidehtiar/hyper-admin
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

First-party plugin **`hyperadmin-tasks`** (`plugins/hyperadmin-tasks/`): a Postgres-native
task-queue integration built on [`pgtask`](https://github.com/Kludex/pgtask) (Kludex, pre-alpha)
behind a backend-agnostic `TaskBackend` port, plus an admin-native "Flower-lite" monitoring UI
(dashboard, tasks, workers, schedules; retry / cancel / pause actions).

SDD: `docs/specs/plugin-tasks.md` (human gate: `reviewspec-approve-sdd-for-plugin-tasks`).

Epics (order):
- `epic-plugin-tasks-foundation` — package scaffold, port, in-memory backend, contract suite (seam, first)
- `epic-plugin-tasks-pgtask-adapter` — experimental pgtask adapter (blocked by foundation port)
- `epic-plugin-tasks-monitoring-ui` — UI on the port (parallel with the adapter, uses in-memory backend)
- `epic-plugin-tasks-integration` — in-process worker, transactional enqueue, example app, docs

Out of scope (v2): enqueue-from-UI, schedule CRUD, SSE live refresh, charts, other backends.
