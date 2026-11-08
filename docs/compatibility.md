# Compatibility & Performance

HyperAdmin is tested two ways: by its own CI suite, and by mounting it on real open-source
FastAPI apps **without changing their models**. This page lists the stacks that work today,
what each real-app run showed, and the timings we measured.

## Supported stacks

| Layer | Supported | How we verify it |
|---|---|---|
| Python | 3.11, 3.12, 3.13, 3.14 | CI runs all four on Ubuntu and 3.11 + 3.14 on macOS. The Polar and Mealie runs used 3.14 |
| FastAPI | 0.116 and later | Runtime dependency, CI |
| Pydantic | v2 (2.10.1+; 2.12+ on Python 3.14) | Runtime dependency, CI lowest/highest resolution |
| SQLModel | 0.0.19+ `table=True` models | CI, ERP and full demo apps, Langflow (SQLModel 0.0.48) |
| SQLAlchemy 2.0 `DeclarativeBase` | `Mapped[...]` / `mapped_column` models, no SQLModel needed | [`examples/sqlalchemy/`](examples.md#sqlalchemy-plain-sqlalchemy-20), Polar (138 models) |
| Legacy `declarative_base()` | Classic declarative models | Open WebUI (44 models) |
| SQLAlchemy 2.1 | 2.1.x | Mealie (SQLAlchemy 2.1.6) |
| Sync SQLAlchemy apps | The host writes with a sync engine and HyperAdmin reads the same database through an async driver | Mealie |
| Databases | SQLite (`aiosqlite`), PostgreSQL (async driver, for example `asyncpg`) | CI and examples on SQLite; Polar and the load-test stack on PostgreSQL |
| Primary keys | `int`, `uuid.UUID`, natural `str`; composite keys are list-only | CI, [Bring your own app](guides/existing-app.md), Polar, Open WebUI |
| Auth | Built-in session auth with MFA, or your own auth through `ExternalAuth` | CI, [`examples/byoa/`](examples.md#byoa-bring-your-own-app) |

Column types that work without configuration include enums (`SAEnum` and enums wrapped in a
`TypeDecorator`), JSON and JSONB, `server_default` timestamps, timezone-aware datetimes,
deferred columns (left out of lists and forms), and single-table-inheritance subclasses.

MySQL has not been verified yet. The run that covers it, on fastapi_best_architecture
([#712](https://github.com/yevheniidehtiar/hyper-admin/issues/712)), is still to come.

## Tested on real open-source apps

Each run follows the same rules:

- The app is pinned to an exact commit, and its models are not modified. Anything we had to
  change became a HyperAdmin issue.
- The database is migrated with the app's own tooling and seeded with the app's own factories
  where it has them, or with a generic seeder.
- A probe script registers every mapped model and requests the list, search, sort, create,
  detail and edit pages of each one, in-process through the ASGI app.

| App | Stack | Models | Result | Pinned commit |
|---|---|---|---|---|
| [Polar](https://github.com/polarsource/polar) | SQLAlchemy 2.0 `DeclarativeBase`, async, PostgreSQL, Python 3.14 | 138 | list, search and sort 138 / 138 · create 127 / 127 · detail and edit 11 / 11 seeded rows · no exceptions | `64a08ec` |
| [Langflow](https://github.com/langflow-ai/langflow) | SQLModel 0.0.48, SQLAlchemy 2.0.55, SQLite | 61 | list and search 61 / 61 · create 58 / 58 · detail and edit 5 / 5 · auto-discovery found all 61 | `aeb10d9` |
| [Mealie](https://github.com/mealie-recipes/mealie) 3.29.0 | SQLAlchemy 2.1.6, sync app, SQLite, Python 3.14 | 57 | list, search and deep page 57 / 57 · create 50 / 50 · detail and edit 49 / 49 | `b622f9e` |
| [Open WebUI](https://github.com/open-webui/open-webui) | Legacy `declarative_base()`, string primary keys, SQLite | 44 | list and search 44 / 44 · create 43 / 43 · detail and edit 2 / 2 seeded rows | `f7ac7ee` |

Create counts leave out tables with a composite primary key (11 in Polar, 3 in Langflow, 7 in
Mealie, 1 in Open WebUI). Those register as list-only by design.

Polar is also the head-to-head benchmark: it has a hand-built FastAPI + HTMX back office, and
the comparison write-up is tracked in
[#703](https://github.com/yevheniidehtiar/hyper-admin/issues/703).

### What the runs fixed

The first Polar run rendered 1 list page out of 138. These fixes, all merged, took it to 138 / 138
and made the other targets work:

| Problem | Found on | Issue |
|---|---|---|
| SQLAlchemy 2.0 `DeclarativeBase` models had no adapter | Polar | [#715](https://github.com/yevheniidehtiar/hyper-admin/issues/715) |
| Views read Pydantic `model_fields`, which plain SQLAlchemy models lack. HyperAdmin now builds a schema from the mapper (`hyperadmin.core.schema_for`) | Polar | [#719](https://github.com/yevheniidehtiar/hyper-admin/issues/719) |
| Joined-eager collections returned duplicate rows | Polar | [#718](https://github.com/yevheniidehtiar/hyper-admin/issues/718) |
| Deferred columns (a `TSVECTOR` search vector) raised `DetachedInstanceError` | Polar | [#719](https://github.com/yevheniidehtiar/hyper-admin/issues/719) |
| A 1,500-message JSON column made one list page 1.95 MB. JSON columns are now left out of default list columns and shortened to a one-line preview | Open WebUI | [#767](https://github.com/yevheniidehtiar/hyper-admin/issues/767) |
| Mount failed on Python 3.14 when relationship types were imported only under `TYPE_CHECKING` | Mealie | [#770](https://github.com/yevheniidehtiar/hyper-admin/issues/770) |
| Columns annotated with a SQLAlchemy `TypeDecorator` (`Mapped[GUID]`) broke detail and edit | Mealie | [#772](https://github.com/yevheniidehtiar/hyper-admin/issues/772) |
| A lazy relationship named `label` or `name` broke the row title | Mealie | [#773](https://github.com/yevheniidehtiar/hyper-admin/issues/773) |

### Still to run

Prefect, Arize Phoenix, Apache Airflow 3, freqtrade, fastapi_best_architecture (MySQL), Agenta,
SkyPilot and the full-stack-fastapi-template. Progress is tracked in epic
[#701](https://github.com/yevheniidehtiar/hyper-admin/issues/701).

## Performance

Measured on Mealie with 237,757 rows across 66 tables in one SQLite file (133 MB). Requests
went through the ASGI app in-process (no network), with the default page size of 10. Each
figure is the median of 3 runs. "Deep page" is the page halfway through the table.

| Model | Rows | List | Deep page | Search | Detail |
|---|---:|---:|---:|---:|---:|
| RecipeIngredientModel | 100,000 | 112 ms | 126 ms | 172 ms | 9 ms |
| RecipeInstruction | 80,000 | 33 ms | 41 ms | 79 ms | 8 ms |
| RecipeModel | 20,000 | 71 ms | 76 ms | 102 ms | 9 ms |
| Note | 20,000 | 34 ms | 29 ms | 37 ms | 9 ms |
| ShoppingListItem | 5,000 | 117 ms | 118 ms | 119 ms | 9 ms |
| RecipeComment | 5,000 | 77 ms | 79 ms | 82 ms | 9 ms |
| IngredientFoodModel | 3,000 | 28 ms | 26 ms | 29 ms | 8 ms |

What the numbers show:

- **Deep pages cost the same as the first page.** At 100,000 rows we saw no offset penalty on
  SQLite.
- **Search is the slowest operation**, 172 ms at 100,000 rows. It is a `LIKE` scan over the
  inferred text columns. Set `search_fields` to fewer columns to make it cheaper.
- **The number of columns matters more than the number of rows.** `ShoppingListItem` (5,000
  rows) is slower than `Note` (20,000 rows) because it renders more columns. Trim
  `list_display` on wide models.
- **Detail pages take about 9 ms** at every table size.
- **Startup is cheap.** Registering 57 models and building their routes took 0.8 s.

These are SQLite figures, so treat them as a floor for query cost, not a forecast for
production. The next section covers PostgreSQL under concurrent users.

### Under load

The ERP example on PostgreSQL 16 with 100,000 seeded rows. App and database share one Docker
VM with 9 CPUs (PostgreSQL capped at 2); the app runs 9 uvicorn workers with a pool of 10 + 10
connections each and `--limit-concurrency 100`. Locust runs outside the VM: 90% of users browse
(list, search, sort, detail, foreign-key choices) and 10% create, update and delete contacts,
each waiting 0.5–3 s between requests. Numbers exclude the ramp-up.

| Users | Successful req/s | Median | p95 | p99 | Errors |
|---:|---:|---:|---:|---:|---:|
| 400 | 296 | 21 ms | 170 ms | 620 ms | 0% |
| 800 | 270 | 1.2 s | 4.0 s | 6.4 s | 0.03% |

At 400 users every page has a median of 9–35 ms and a p95 under 300 ms; writes are the
slowest. At 800 users both the app (about 7.4 CPUs) and PostgreSQL (at its 2-CPU cap) are
saturated, so throughput stays near 300 req/s and requests wait instead. Size for about
**30 req/s per CPU** of app plus database at this page mix.

What we learned sizing it:

- **Size the pool per worker.** Each uvicorn worker has its own pool. SQLAlchemy's default
  (5 + 10, 30 s timeout) times out with 500s once a worker falls behind; workers x (pool +
  overflow) must stay under PostgreSQL's `max_connections`.
- **Turn excess load away early.** `uvicorn --limit-concurrency` answers 503 straight away
  when a worker is full, instead of queueing requests until the pool times out.
- **SQLite is for one worker and light writes.** Under concurrent writes it raises
  `database is locked`; use PostgreSQL for anything multi-user.

### Connection pool

Under load, requests queue for a database connection once the pool is used up. SQLAlchemy's
default pool holds 5 connections plus 10 overflow, and a request waits 30 seconds for one
before it fails. When HyperAdmin builds the engine from `database_url` (no `engine=`
passed), set the pool through settings or environment variables:

| Setting | Environment variable | SQLAlchemy argument |
|---|---|---|
| `database_pool_size` | `HYPERADMIN_DATABASE_POOL_SIZE` | `pool_size` |
| `database_max_overflow` | `HYPERADMIN_DATABASE_MAX_OVERFLOW` | `max_overflow` |
| `database_pool_timeout` | `HYPERADMIN_DATABASE_POOL_TIMEOUT` | `pool_timeout` |
| `database_pool_recycle` | `HYPERADMIN_DATABASE_POOL_RECYCLE` | `pool_recycle` |
| `database_pool_pre_ping` | `HYPERADMIN_DATABASE_POOL_PRE_PING` | `pool_pre_ping` |

When you pass your own engine, build it with the same arguments. `build_engine` drops the
pool sizing for an in-memory SQLite URL, so one configuration works in tests too:

```python
from hyperadmin.db import build_engine

engine = build_engine(
    DATABASE_URL,
    {"pool_size": 20, "max_overflow": 40, "pool_timeout": 30, "pool_pre_ping": True},
)
admin = Admin(app, engine=engine)
```

These values are a starting point for PostgreSQL, not a measured optimum. Each worker
process has its own pool, so keep `workers * (pool_size + max_overflow)` below the server's
`max_connections`.

### Rate limiting

A traffic spike goes straight to the database. HyperAdmin can answer `429 Too Many
Requests` with a `Retry-After` header once one client passes a limit. It is off until you
set one:

| Setting | Environment variable | Meaning |
|---|---|---|
| `rate_limit_requests` | `HYPERADMIN_RATE_LIMIT_REQUESTS` | Admin requests one client may make per window |
| `rate_limit_login_requests` | `HYPERADMIN_RATE_LIMIT_LOGIN_REQUESTS` | A further limit on login form submissions |
| `rate_limit_window_seconds` | `HYPERADMIN_RATE_LIMIT_WINDOW_SECONDS` | Window length, 60 by default |

The limiter is a token bucket: a client may burst up to the limit, then sustains the
average rate. Static assets are never counted, and host routes outside the admin prefix are
not touched. The login limit is the one that slows password guessing, so set it low (for
example 5 per minute).

Three things to know before you rely on it:

- **Counts are per process.** With 3 workers a client gets up to 3 times the limit. To
  enforce one limit across workers, pass your own shared implementation of
  `hyperadmin.core.rate_limit.RateLimiter` (a single `async acquire(key)` method) as
  `Admin(app, rate_limiter=...)`.
- **Behind a reverse proxy, the client is the proxy** unless the server rewrites the client
  address. Run uvicorn with `--proxy-headers` and `--forwarded-allow-ips` set to your
  proxy. HyperAdmin never reads `X-Forwarded-For` itself, because any client could forge it
  to escape the limit.
- **It protects the admin only.** A limiter on a gateway or CDN in front of the whole app
  is still the better place for broad abuse protection.

### Load testing your own deployment

HyperAdmin ships a Locust suite and a synthetic data generator for measuring a real
deployment. Install the `loadtest` extra and use the ERP example's stack: PostgreSQL 16, the
app with 3 workers, and a Locust master and worker.

```bash
uv sync --extra loadtest
docker compose -f docker-compose.loadtest.yml up --build
```

`hyperadmin seed` bulk-inserts Faker data, including foreign keys with a realistic skew, and
can resume an interrupted run. The Locust users cover the read pages (list, search, detail) and
create and update writes, and log in once per user; `LOADTEST_LOGIN_SESSIONS=N` caps that at
`N` logins per Locust process, shared by the rest, so password hashing does not swamp a large
run. `examples/erp/loadtest/baselines.py`
records a baseline and compares later runs against it.

To compare setups, `scripts/loadtest_matrix.sh` runs the same test across database, app CPUs,
users and realtime backend, and writes a summary table to `reports/loadtest-matrix/`:

```bash
./scripts/loadtest_matrix.sh                      # the whole matrix
./scripts/loadtest_matrix.sh pg-4cpu-400u         # chosen rows only
SEED_ROWS=0 ./scripts/loadtest_matrix.sh          # reuse the data already seeded
```

It gives the app a hard CPU limit with one worker per CPU and stops a row early once the app
log shows overload (`Exceeded concurrency limit`, `QueuePool limit`, `database is locked`, a
traceback), skipping heavier rows for that setup. Run it on an otherwise idle machine: Locust
runs on the host, and other work there starves it and skews the numbers.

## Known limitations

| Limitation | Workaround | Issue |
|---|---|---|
| `auto_discover` finds SQLModel models only | Register plain SQLAlchemy models explicitly with `site.register(Model)` | [#716](https://github.com/yevheniidehtiar/hyper-admin/issues/716) |
| `hybrid_property` and `column_property` attributes can't be shown as columns | Use a real column, or a custom template | [#731](https://github.com/yevheniidehtiar/hyper-admin/issues/731) |
| Epoch-integer timestamps show as plain integers | None yet | [#768](https://github.com/yevheniidehtiar/hyper-admin/issues/768) |
| A `Boolean` column annotated as `str` is searched with `ILIKE` and fails on PostgreSQL | Leave that column out of `search_fields` | [#778](https://github.com/yevheniidehtiar/hyper-admin/issues/778) |
| Tables with a composite primary key are list-only (no create, detail or edit pages) | By design | n/a |
| `create_tables=True` creates SQLModel tables only | A plain SQLAlchemy app creates its schema with its own migrations or `Base.metadata.create_all` | n/a |

---

Next: [Examples](examples.md)
