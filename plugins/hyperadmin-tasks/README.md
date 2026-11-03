# hyperadmin-tasks

First-party HyperAdmin plugin that adds a background task dashboard under `{prefix}/tasks`.

This package is the foundation scaffold: it registers the plugin, a "Tasks" sidebar section,
the `view_tasks` and `manage_tasks` permissions, and a placeholder dashboard page gated on
`view_tasks`. See `docs/specs/plugin-tasks.md` for the full design.

Disable it with `disabled_plugins=["tasks"]`.

## Running a worker

pgtask runs your task handlers in a worker. Define them on one or more pgtask `TaskRegistry`
objects (one per queue).

### In the admin process (development, small deploys)

Set `HYPERADMIN_TASKS_RUN_WORKER=true` and compose the plugin lifespan in your app:

```python
from contextlib import asynccontextmanager

import hyperadmin_tasks
from myapp.tasks import registry  # a pgtask TaskRegistry


@asynccontextmanager
async def lifespan(app):
    async with admin.lifespan(), hyperadmin_tasks.lifespan(admin, registries=[registry]):
        yield
```

Instead of `registries=`, you can set `HYPERADMIN_TASKS_REGISTRIES="myapp.tasks:registry"` (a
registry or a list of them). The worker connects with `HYPERADMIN_TASKS_WORKER_DSN` (the pgtask
worker role), falling back to `HYPERADMIN_TASKS_DSN`. On shutdown, running handlers get
`HYPERADMIN_TASKS_WORKER_SHUTDOWN_GRACE` seconds (default 30) to finish; pgtask then cancels them
and returns their tasks to `pending`. `HYPERADMIN_TASKS_WORKER_CONCURRENCY` (default 10) caps how
many handlers run at once.

With several web workers (for example `uvicorn --workers 4`), each process runs its own worker.

### As a separate process (production)

Leave `run_worker` off and run the worker on its own, with the same registries:

```python
# worker.py
import asyncio

from pgtask import Worker

from myapp.tasks import registry


async def main() -> None:
    await Worker("postgresql://worker@db/app", registry).run()


asyncio.run(main())
```
