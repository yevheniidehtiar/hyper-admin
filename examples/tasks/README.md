# Background tasks example

HyperAdmin with the `hyperadmin-tasks` plugin on [pgtask](https://pypi.org/project/pgtask/) and
Postgres 16. One FastAPI process serves the admin and runs a pgtask worker. Admin actions enqueue
tasks in the same transaction as the row they change, and the Tasks dashboard shows each run.

## Boot

With Docker:

```bash
docker compose -f examples/tasks/docker-compose.yml up --build
```

Open <http://127.0.0.1:8000/admin/report>.

Without Docker, start only the database and run the app from the repository root:

```bash
docker compose -f examples/tasks/docker-compose.yml up -d db
uv sync --all-extras --all-packages      # --all-packages installs pgtask (hyperadmin-tasks[pgtask])
uv run uvicorn examples.tasks.main:app   # DATABASE_URL defaults to the compose database
```

On startup the app creates the `report` table, migrates the pgtask schema, stores the
`reports-digest` cron schedule and seeds three reports. Run `docker compose ... down -v` to start
over.

## Try it

### A task that succeeds

1. On **Reports**, open "Weekly sales" and run **Generate report**. Its status becomes `queued`.
2. Open **Tasks**. `reports.generate` runs for about two seconds, then shows `succeeded` with its
   result.
3. Back on **Reports**, "Weekly sales" is `ready` and has a row count.

### A task that fails and is retried

1. Run **Deliver report** on any report.
2. In **Tasks**, `reports.deliver` fails three times. The pretend webhook is down, and the task
   ends in `failed`. Its detail page lists each attempt and its error.
3. Press **Retry**. The webhook is back for this run, so the task succeeds and the report becomes
   `delivered`.

### A cron schedule

**Tasks → Schedules** lists `reports-digest`, which runs `reports.digest` at the start of every
minute. Pause and resume it from there. pgtask cron expressions have six fields, seconds first
(`0 * * * * *`).

## How it is wired

| What | Where |
|---|---|
| Task handlers on a pgtask `TaskRegistry` | `tasks.py` |
| Admin actions that call `enqueue_in_session()` | `admin.py` (`enqueue_for`) |
| Plugin settings and the composed lifespan | `main.py` (`TASKS_SETTINGS`, `lifespan`) |
| psycopg engine (`postgresql+psycopg://`), needed for `enqueue_in_session()` | `db.py` |

The example uses one database role for everything. In production, give the app, the worker and
the dashboard their own pgtask roles (`pgtask.configure_grants`), and run the worker as its own
process. See `plugins/hyperadmin-tasks/README.md`.
