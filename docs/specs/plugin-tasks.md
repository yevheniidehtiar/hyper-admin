# SDD: hyperadmin-tasks — Postgres task-queue monitoring plugin (pgtask)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | #739 (epic `epic-plugin-tasks-foundation`) |
| Milestone | v0.8.1 — Tasks plugin (pgtask, experimental) |
| Created | 2026-10-29 |
| Last updated | 2026-10-29 |

---

## Problem

HyperAdmin users who run background work today need Celery, Redis and Flower: three extra pieces of
infrastructure and a separate UI with its own auth. Many HyperAdmin deployments already run
PostgreSQL. [`pgtask`](https://github.com/Kludex/pgtask) (Kludex, MIT) is a Postgres-only task and
workflow engine that does not need a broker. It provides LISTEN/NOTIFY dispatch, leases, retries,
cron schedules, durable steps, transactional enqueue, observer SQL views and audited admin actions.

pgtask ships a standalone `pgtask-web` UI. That UI cannot be mounted in an ASGI app and expects an
auth proxy to inject the identity header. HyperAdmin already has auth, permissions, layout and HTMX.
A plugin can therefore give an admin-native, permission-gated "Flower-lite" view of the queues.

**Maturity caveat:** pgtask is `Development Status :: 2 - Pre-Alpha` (v0.4.0, 2026-10-07). Its
public API differs between the PyPI README and `main`. Observer view **columns are not a stable
contract**; only SQL function signatures are. The design isolates pgtask behind a port so that
churn stays in one module.

## Goals

- A new first-party plugin package, `plugins/hyperadmin-tasks/` (PyPI: `hyperadmin-tasks`), loaded
  through the `hyperadmin.plugins` entry point.
- A backend-agnostic `TaskBackend` port with read models and capability flags.
  - Ships with an `InMemoryTaskBackend` for tests and demos.
  - Ships with a reusable contract test suite.
- A `PgTaskBackend` adapter behind the `[pgtask]` extra, marked **experimental**.
- A monitoring UI covering the dashboard, queues, task list and detail, workers and schedules.
- Safe actions: retry, cancel, queue pause/resume and schedule pause/resume. They are gated by
  `manage_tasks` and the actor is audited.
- Integration helpers:
  - An optional in-process worker tied to the admin lifespan.
  - Transactional enqueue from a SQLAlchemy `AsyncSession` on the psycopg driver.
- An example app, plus docs that include a "Coming from Celery" guide.

## Non-Goals

- Moving HyperAdmin's own features (exports, bulk actions, reports) onto a queue.
- Enqueue-from-UI forms, schedule CRUD, SSE live updates, charts (planned for v2, built on the port).
- Adapters other than pgtask (procrastinate, Celery). The port allows them later.
- Any change to `src/hyperadmin/core/`, except a separately reviewed seam PR if one proves necessary
  (see Open Questions).

## BDD Scenarios

```
Scenario: plugin registers Tasks pages for an authorised user
  Given hyperadmin-tasks is installed and configured with the in-memory backend
  And   the user has the view_tasks permission
  When  the user opens /admin/tasks
  Then  the sidebar shows a "Tasks" section
  And   the dashboard lists every queue with ready, running, failed and scheduled counts

Scenario: user without view_tasks is denied
  Given the user lacks view_tasks
  When  the user requests /admin/tasks
  Then  the response is 403 and the Tasks nav section is hidden

Scenario: failed task is retried from the admin
  Given a task in state "failed" on queue "reports"
  And   the user has manage_tasks
  When  the user clicks "Retry" on the task detail page and confirms
  Then  the backend receives retry_task(task_id, actor=<username>)
  And   the task state becomes "pending"
  And   a success flash message is shown

Scenario: actions are hidden when the backend lacks the capability
  Given a backend whose capabilities exclude CANCEL
  When  the user opens a running task's detail page
  Then  no "Cancel" button is rendered

Scenario: incompatible pgtask storage protocol fails fast
  Given the database reports a storage_protocol_range that excludes the adapter's supported version
  When  the admin starts up
  Then  startup fails with a TasksBackendError naming both versions and the supported pgtask range

Scenario: transactional enqueue rolls back with the business write
  Given an AsyncSession bound to a postgresql+psycopg engine
  When  a row is inserted, enqueue_in_session(session, request) is called, and the transaction rolls back
  Then  neither the row nor the task exists
```

## Design

### Architecture

```
plugins/hyperadmin-tasks/src/hyperadmin_tasks/
  plugin.py            TasksPlugin (name="tasks", settings_model=TasksSettings)
  settings.py          TasksSettings
  backend.py           TaskBackend protocol, read models, Capability, TasksBackendError
  backends/memory.py   InMemoryTaskBackend
  backends/pgtask.py   PgTaskBackend  ← only module importing pgtask / psycopg
  contract.py          backend contract test suite (importable by third-party adapters)
  routes.py            build_router(admin) → APIRouter
  integration.py       run_worker_in_lifespan(), enqueue_in_session()
  templates/tasks/     dashboard, task_list, task_detail, workers, schedules, _partials
```

The dependency flow is `routes → backend (port) ← backends/*`. The core never imports the plugin.
The plugin uses only public seams in `hyperadmin.core.plugins`: `add_page`, `add_nav_entry`,
`add_template_dir`, `set_static_dir`, `add_permission` and `settings_model`.

### Data Model Changes

HyperAdmin's database has no data model changes. pgtask owns the `pgtask` schema and its
migrations (`Client.migrate()` / `pgtask migrate`). Read models are frozen pydantic models:

| Model | Fields |
|---|---|
| `QueueStats` | `name`, `ready`, `running`, `scheduled`, `failed`, `succeeded_recent`, `oldest_ready_age: timedelta \| None`, `paused: bool` |
| `TaskRecord` | `id`, `queue`, `name`, `state: TaskState`, `priority`, `attempt`, `max_attempts`, `created_at`, `run_at`, `finished_at`, `payload`, `result`, `error`, `parent_id` |
| `AttemptRecord` | `number`, `worker_id`, `started_at`, `finished_at`, `outcome`, `error` |
| `WorkerRecord` | `id`, `queues`, `task_names`, `last_seen_at`, `concurrency`, `healthy` |
| `ScheduleRecord` | `id`, `task_name`, `queue`, `cron`, `next_run_at`, `misfire_policy`, `paused` |
| `TaskFilter` | `queue`, `state`, `name`, `id_query` |
| `Page[T]` | `items`, `page`, `per_page`, `total \| None` |

`TaskState` is an enum: `pending`, `scheduled`, `running`, `sleeping`, `waiting`, `succeeded`,
`failed`, `cancelled`. Each adapter maps its native states onto it.

### API / Protocol Changes

```python
class Capability(StrEnum):
    RETRY = "retry"; CANCEL = "cancel"; PAUSE_QUEUE = "pause_queue"
    PAUSE_SCHEDULE = "pause_schedule"; SCHEDULES = "schedules"; WORKERS = "workers"

class TaskBackend(Protocol):
    capabilities: frozenset[Capability]
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def list_queues(self) -> list[QueueStats]: ...
    async def list_tasks(self, flt: TaskFilter, page: int, per_page: int) -> Page[TaskRecord]: ...
    async def get_task(self, task_id: str) -> tuple[TaskRecord, list[AttemptRecord]] | None: ...
    async def list_workers(self) -> list[WorkerRecord]: ...
    async def list_schedules(self) -> list[ScheduleRecord]: ...
    async def retry_task(self, task_id: str, *, actor: str) -> None: ...
    async def cancel_task(self, task_id: str, *, actor: str) -> None: ...
    async def set_queue_paused(self, queue: str, paused: bool, *, actor: str) -> None: ...
    async def set_schedule_paused(self, schedule_id: str, paused: bool, *, actor: str) -> None: ...
```

Calling an action outside `capabilities` raises `TasksBackendError`.

HTTP routes are mounted under the `/tasks` prefix in the `hyperadmin:` namespace:

| Method | Path | Permission |
|---|---|---|
| GET | `/tasks` (dashboard; `?partial=1` for HTMX refresh) | `view_tasks` |
| GET | `/tasks/list` | `view_tasks` |
| GET | `/tasks/t/{task_id}` | `view_tasks` |
| GET | `/tasks/workers`, `/tasks/schedules` | `view_tasks` |
| POST | `/tasks/t/{task_id}/retry`, `/tasks/t/{task_id}/cancel` | `manage_tasks` |
| POST | `/tasks/queues/{name}/pause`, `/tasks/queues/{name}/resume` | `manage_tasks` |
| POST | `/tasks/schedules/{id}/pause`, `/tasks/schedules/{id}/resume` | `manage_tasks` |

All POSTs use the core CSRF protection.

**pgtask adapter mapping**
- Reads use a separate observer-role connection, querying only the security-barrier observer views:
  - `queue_overview`, `task_view`, `attempt_view`, `worker_view`, `schedule_view`.
- Actions use an administrator-role connection and call pgtask's administrator functions. The
  HyperAdmin username is passed as the actor, so `pgtask.administrator_audit` records it.
- Column names are mapped in a single `_columns.py` table. A startup probe validates the expected
  columns and raises a clear error on drift.
- The version range is pinned to `pgtask>=0.4,<0.5`.

### Configuration Changes

`TasksSettings` is a pydantic-settings model with the `HYPERADMIN_TASKS_` prefix.

| Field | Default | Notes |
|---|---|---|
| `backend` | `"memory"` | `"memory"` \| `"pgtask"` \| dotted path to a `TaskBackend` factory |
| `dsn` | `None` | administrator-role DSN (actions) |
| `observer_dsn` | `None` | observer-role DSN (reads); falls back to `dsn` with a warning |
| `refresh_seconds` | `5` | HTMX polling interval; `0` disables |
| `page_size` | `50` | |
| `run_worker` | `False` | start an in-process pgtask `Worker` in the admin lifespan (dev / small deploys) |

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `[pgtask]` extra not installed but `backend="pgtask"` | `TasksBackendError` at registration: "install hyperadmin-tasks[pgtask]" |
| Postgres < 16 or pgtask schema not migrated | Startup probe error naming the missing schema and the `pgtask migrate` command |
| Storage protocol out of range | Fail fast (see scenario) |
| Observer view column drift | Startup probe lists missing or renamed columns; the plugin stays disabled and the rest of the admin keeps working |
| Backend unreachable during a request | Page renders an inline error banner (`data-testid="tasks-backend-error"`), and polling backs off |
| Task deleted by retention between list and detail | 404 page with a link back to the list |
| Concurrent retry/cancel race | Backend error surfaced as a flash message; no 500 |
| Engine uses asyncpg for transactional enqueue | `TasksBackendError`: psycopg driver required |
| Huge payload / result JSON | Truncated preview with an expandable full view; render capped at 64 KiB |

## Migration & Backward Compatibility

This is a new opt-in package, so no migration is required. The plugin is marked experimental in the
docs and its version range is pinned to pgtask's minor version.

## Open Questions

- [x] Do the plugin seams expose an async startup/shutdown hook for opening and closing the
      adapter's pool? If not, a minimal `feat(core)` seam PR is needed (story T1.6, conditional).
      Resolved 2026-10-29: no core seam. The plugin starts the backend lazily on first use from
      its routes (`BackendLifecycle`) and ships `hyperadmin_tasks.lifespan(admin)` for hosts that
      want eager start and a clean `backend.shutdown()`.
- [ ] Are the pgtask administrator SQL functions for retry, cancel and queue pause public and stable?
      The docs name `put_schedule` but not the cancel and retry functions. If they aren't, call the
      Python client and pass the actor header.
- [ ] Should the plugin carry its own audit log in addition to `pgtask.administrator_audit`? The
      recommendation is no for v1.
- [ ] Root extra `hyper-admin[tasks]`, or a separate install only? The recommendation is a separate
      install, matching `hyperadmin-reports`.
- [ ] HTMX polling vs. pubsub/SSE refresh. Polling is used for v1; SSE through `realtime/` is v2.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Thin `TaskBackend` port with pgtask as the first adapter | pgtask is pre-alpha; contain churn and allow other backends later | Bind directly to pgtask; ship multiple backends in v1 |
| Admin-native UI instead of embedding `pgtask-web` | `pgtask-web` is a separate binary with proxy-header auth and cannot be mounted | Reverse-proxy `pgtask-web` under `/admin` |
| Read via observer views, act via the administrator role | Least privilege and native audit trail | Single owner DSN |
| Backend lifecycle owned by the plugin: lazy `startup()` on first route use plus `hyperadmin_tasks.lifespan(admin)` | Core has no async plugin startup seam and the owner asked to start without a core change | `feat(core)` async startup/shutdown seam PR first |
| HTMX polling for refresh | No new infrastructure; matches existing patterns | SSE through the `realtime/` pubsub |
| Integration and monitoring only | Keep core task-agnostic (CONSTITUTION §4, §7) | Offload core exports and bulk actions |
