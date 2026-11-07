# Background Tasks

!!! warning "Experimental"

    `hyperadmin-tasks` 0.1 runs on [pgtask](https://github.com/Kludex/pgtask), which is
    **pre-alpha** (`Development Status :: 2 - Pre-Alpha`). The `[pgtask]` extra pins
    `pgtask>=0.4,<0.5`. Keep that pin: pgtask's Python API and its observer view columns change
    between releases. Expect breaking changes in both packages before 1.0.

The `hyperadmin-tasks` plugin adds a background task dashboard to the admin, backed by pgtask. It
is a Postgres-only task queue: no broker, no Redis, no separate monitoring UI.

Under `/admin/tasks` you get:

- **Dashboard:** every queue with its ready, running, scheduled and failed counts.
- **Tasks:** a filterable task list, and a detail page with the payload, the result and every
  attempt with its error.
- **Workers** and **Schedules**.
- **Actions:** retry and cancel a task, pause and resume a schedule. pgtask records each action,
  with the admin username, in `pgtask.administrator_audit`.

Two permissions gate the pages: `view_tasks` for reading and `manage_tasks` for the actions.

## Install

The plugin is not on PyPI yet. Install it from the repository, with the `[pgtask]` extra:

```bash
uv add "hyperadmin-tasks[pgtask] @ git+https://github.com/yevheniidehtiar/hyper-admin#subdirectory=plugins/hyperadmin-tasks"
```

This also installs `hyper-admin` from the same commit. Add `@<commit>` after the repository URL to
pin both.

HyperAdmin discovers installed plugins through the `hyperadmin.plugins` entry point, so the
sidebar shows **Tasks** with no code change. Turn it off with `Admin(disabled_plugins=["tasks"])`.

Postgres 16 or later is required. Before first use, create the pgtask schema once, as the database
owner:

```python
from pgtask import Client

client = await Client.connect("postgresql://owner@db/app")
await client.migrate()
```

## Settings

Set the plugin's settings as `HYPERADMIN_TASKS_*` environment variables, or pass them to `Admin`:

```python
Admin(app, engine=engine, plugin_settings={"tasks": {"backend": "pgtask", "dsn": "postgresql://..."}})
```

| Setting | Environment variable | Default | Meaning |
|---|---|---|---|
| `backend` | `HYPERADMIN_TASKS_BACKEND` | `"memory"` | `"pgtask"`, `"memory"` (in-process, no database; for tests and UI work), or a `"module:attr"` backend factory |
| `dsn` | `HYPERADMIN_TASKS_DSN` | `None` | administrator-role DSN, used for the actions |
| `observer_dsn` | `HYPERADMIN_TASKS_OBSERVER_DSN` | `None` | observer-role DSN, used for the read-only pages. Falls back to `dsn`, with a warning |
| `refresh_seconds` | `HYPERADMIN_TASKS_REFRESH_SECONDS` | `5` | dashboard auto-refresh interval; `0` turns it off |
| `page_size` | `HYPERADMIN_TASKS_PAGE_SIZE` | `50` | rows per page in task lists |
| `run_worker` | `HYPERADMIN_TASKS_RUN_WORKER` | `false` | run a pgtask worker inside the admin process (see below) |
| `worker_dsn` | `HYPERADMIN_TASKS_WORKER_DSN` | `None` | worker-role DSN for that worker. Falls back to `dsn` |
| `registries` | `HYPERADMIN_TASKS_REGISTRIES` | `None` | `"module:attr"` path to the `TaskRegistry` (or list of them) the worker runs |
| `worker_concurrency` | `HYPERADMIN_TASKS_WORKER_CONCURRENCY` | `10` | handlers the worker runs at once |
| `worker_shutdown_grace` | `HYPERADMIN_TASKS_WORKER_SHUTDOWN_GRACE` | `30.0` | seconds running handlers get to finish on shutdown, before pgtask cancels them and returns their tasks to `pending` |

## Database roles

pgtask has five roles. Grant them with the `pgtask.configure_grants` SQL function, after
`migrate()`, as the owner. The arguments, in order, are owner, producer, worker, observer and
administrator:

```sql
CREATE ROLE pgtask_producer NOLOGIN;
CREATE ROLE pgtask_worker LOGIN PASSWORD '...';
CREATE ROLE pgtask_observer LOGIN PASSWORD '...';
CREATE ROLE pgtask_administrator LOGIN PASSWORD '...';

SELECT pgtask.configure_grants(
    'app_owner', 'pgtask_producer', 'pgtask_worker', 'pgtask_observer', 'pgtask_administrator'
);

-- Your application's own login role enqueues tasks:
GRANT pgtask_producer TO app;
```

Each connection then uses the narrowest role:

| Connection | Role | Can |
|---|---|---|
| `observer_dsn` (dashboard pages) | observer | read the `pgtask.*_view` views, not the tables |
| `dsn` (dashboard actions) | administrator | call the audited `pgtask.admin_*` functions |
| `worker_dsn`, or a separate worker process | worker | claim, run and complete tasks |
| your app's engine | a member of producer | enqueue tasks, including through `enqueue_in_session()` |
| migrations | owner | run `Client.migrate()` |

One superuser DSN for everything works for local development. The
[`examples/tasks`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/examples/tasks) app
does that to stay short.

## Define and run tasks

Handlers live on a pgtask `TaskRegistry`, one per queue:

```python
# myapp/tasks.py
from pgtask import Task, TaskRegistry

registry = TaskRegistry("default")


@registry.task("app.send_invoice", retry_delay=2.0)
async def send_invoice(task: Task, payload: dict[str, int]) -> str:
    ...
    return "sent"
```

A worker runs them. For development and small deploys, run it in the admin process: set
`run_worker` and compose the plugin's lifespan with your app's:

```python
from contextlib import asynccontextmanager

import hyperadmin_tasks
from myapp.tasks import registry


@asynccontextmanager
async def lifespan(app):
    async with admin.lifespan(), hyperadmin_tasks.lifespan(admin, registries=[registry]):
        yield
```

With several web workers (`uvicorn --workers 4`), each process runs its own pgtask worker. In
production, leave `run_worker` off and run `pgtask.Worker(worker_dsn, registry).run()` as its own
process. See the plugin
[README](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/plugins/hyperadmin-tasks#running-a-worker).

## Enqueue in your own transaction

`enqueue_in_session()` writes the task on the SQLAlchemy session's connection. The task commits or
rolls back with your rows, so you don't need an outbox table:

```python
from hyperadmin_tasks import enqueue_in_session

session.add(order)
await session.flush()
await enqueue_in_session(session, send_invoice.request({"order_id": order.id}))
await session.commit()  # the order and the task land together, or neither does
```

The engine must use the psycopg driver (`postgresql+psycopg://`). With any other driver, asyncpg
included, it raises `TasksBackendError`.

## Schedules

pgtask stores schedules in the database, and every worker fires them. There is no separate beat
process. pgtask 0.4 has no Python API for schedules yet, so create them with the
`pgtask.put_schedule` SQL function. It upserts by name and leaves an unchanged schedule alone,
which keeps a pause set from the dashboard across restarts. The
[example app](https://github.com/yevheniidehtiar/hyper-admin/blob/develop/examples/tasks/tasks.py)
has a working call.

Things to know about pgtask 0.4 schedules:

- **Cron expressions have six fields, seconds first:** `0 * * * * *` is every minute. A five-field
  expression such as `* * * * *` is accepted and then never fires.
- `put_schedule` needs an explicit first `next_run_at`.
- Interval schedules (`kind = 'interval'`, in milliseconds) are also available.

## Retries

A failing handler is retried until it has failed `max_attempts` times (default 5, set it on the
request), waiting `retry_delay` seconds between attempts. Raise `pgtask.NonRetryableError` to fail at
once.

**Retry** on the dashboard gives a failed task one more run. Inside the handler,
`task.failed_attempts` counts the earlier failures. `task.attempt` counts every claim, including
resumes after a durable sleep.

## Coming from Celery

| Celery | pgtask with hyperadmin-tasks |
|---|---|
| Broker (Redis, RabbitMQ) | Postgres. Tasks are rows; workers wake on `LISTEN/NOTIFY` |
| `@app.task` | `@registry.task("name")` on a `TaskRegistry(queue)` |
| `task.delay(...)`, `apply_async(...)` | `await client.enqueue(definition.request(payload))` |
| `transaction.on_commit` or an outbox table | `enqueue_in_session(session, request)`, in the same transaction |
| `countdown=`, `eta=` | `run_at=` |
| `max_retries=`, `default_retry_delay=` | `max_attempts=` on the request, `retry_delay=` on the task |
| `autoretry_for=` | every exception retries; raise `NonRetryableError` to stop |
| `priority=` | `priority=` |
| Queues and routing | one `TaskRegistry` per queue; a worker runs one or more registries |
| Celery beat | database schedules (`pgtask.put_schedule`), fired by the workers |
| `AsyncResult.get()` | `await handle.result(timeout=...)` |
| `revoke()` | **Cancel** on the dashboard, or `client.cancel(task_id)` |
| Flower | `/admin/tasks`, behind HyperAdmin's auth and permissions |
| none | idempotency keys (`idempotency_key=`), durable steps (`task.step`), durable sleeps and signals |

What Celery has and this stack does not:

- **No canvas.** There are no `chain`, `group` or `chord` primitives. A handler can spawn child
  tasks and wait for their results, or enqueue the next step itself.
- **No rate limits.** There is no per-task `rate_limit`; cap throughput with the worker's
  `concurrency` instead.
- **Postgres only.** pgtask needs Postgres 16 or later. There is no other broker and no other
  result backend.
- **No queue pause in the dashboard.** pgtask's queue pause is not audited, so the plugin does not
  offer it. Schedule pause is available.
- **No schedule editing in the dashboard.** You can pause and resume schedules there, but not
  create or edit them.
- **Pre-alpha engine.** See the warning at the top of this page.

## Try it

[`examples/tasks`](https://github.com/yevheniidehtiar/hyper-admin/tree/develop/examples/tasks) runs
the whole stack with `docker compose`:

- a task that succeeds;
- a flaky task that fails, then succeeds when you press Retry;
- a schedule that runs every minute.
