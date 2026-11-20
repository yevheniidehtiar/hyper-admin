# Large Tables and Performance

The defaults suit small and medium databases. When a table grows to millions of rows, a model
has many relations, or many people use the admin at once, a handful of settings keep the list,
form and filter pages fast. This page covers them in the order to apply them: the database and
its connection pool first, then the options of each large model.

Per-model options are set on `AdminOptions`:

```python
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions


class OrderAdmin(ModelAdmin):
    options = AdminOptions(
        list_select_related=["customer"],
        search_fields=["number"],
        count_cache_ttl=30,
        count_estimate_threshold=1_000_000,
        pagination_mode="cursor",
        preload_threshold=500,
        filter_cache_ttl=60,
    )
```

## Where to start

Slow pages on a large table have few causes, and each has one fix. The timings below come from
our scale tests on a 10-million-row SQLite database with every option at its default; on the same
data a healthy list page took 15 to 120 ms and a detail page 3 to 10 ms.

| What you see | Cause | Fix |
|---|---|---|
| Search takes seconds (about 11 s on a table of 4.2 million rows) | `ILIKE '%term%'` over every text column scans the whole table | Name the columns to search: [`search_fields`](#search) |
| The list is slow even on page 1 (2.3 s on 3.4 million rows) | `count(*)` for the pager's total | [`count_cache_ttl` and `count_estimate_threshold`](#list-totals) |
| Pages far into the list are slow (4.6 s halfway through 4.2 million rows) | `OFFSET` reads every skipped row | [`pagination_mode="cursor"`](#deep-pages) |
| Every page of one list is slow (about 1.2 s on 840,000 rows) | Most likely the column the list sorts by has no index | [Index the sort column](#indexes) |
| A list page fails with `DetachedInstanceError` | A template or `__str__` reads a relation the page did not load | [`list_select_related`](#relations-on-list-pages) |
| A form takes long to open and the page is megabytes | A foreign key renders every row of a large table as an option | [`preload_threshold`](#foreign-key-fields) (on by default) |
| Requests fail with a pool timeout under load | Each worker's connection pool is used up | [Connection pool](#connection-pool) |
| Every request reads the signed-in user and its permissions again | Both are loaded per request | `user_cache_ttl`, see [Permission checks](#permission-checks) |

For a table of 10 million rows or more, apply them in this order:

1. Run PostgreSQL, not SQLite, and keep its statistics fresh (`ANALYZE`, or autovacuum).
2. Index the foreign-key columns, the column the list sorts by and the columns in `list_filter`.
3. Set `search_fields` to one or two indexed columns, or to `[]` when nobody searches the table.
4. Set `count_estimate_threshold` so the unfiltered list never counts, and `count_cache_ttl` for
   the filtered ones.
5. Set `pagination_mode="cursor"` when people page far into the list.
6. Leave `preload_threshold` and `filter_cache_ttl` at their defaults.

Together:

```python
class EventAdmin(ModelAdmin):
    options = AdminOptions(
        list_display=["id", "kind", "account", "created_at"],
        list_filter=["kind"],
        search_fields=["reference"],
        count_cache_ttl=60,
        count_estimate_threshold=1_000_000,
        pagination_mode="cursor",
    )
```

All settings on this page, with their defaults:

| Setting | Set on | Default | Section |
|---|---|---|---|
| `list_select_related` | `AdminOptions` | `None` | [Relations on list pages](#relations-on-list-pages) |
| `auto_select_related` | `AdminOptions` | `True` | [Relations on list pages](#relations-on-list-pages) |
| `detail_select_related` | `AdminOptions` | `None` (every relation) | [Relations on list pages](#relations-on-list-pages) |
| `search_fields` | `AdminOptions` | `None` (every text column) | [Search](#search) |
| `count_cache_ttl` | `AdminOptions` | `0` (off) | [List totals](#list-totals) |
| `count_estimate_threshold` | `AdminOptions` | `None` (off) | [List totals](#list-totals) |
| `count_cache_max_entries` | `HyperAdminSettings` | `1024` | [List totals](#list-totals) |
| `pagination_mode` | `AdminOptions` | `"offset"` | [Deep pages](#deep-pages) |
| `preload_threshold` | `AdminOptions` | `500` | [Foreign-key fields](#foreign-key-fields) |
| `filter_cache_ttl` | `AdminOptions` | `60` | [List filters](#list-filters) |
| `database_pool_size`, `database_max_overflow`, `database_pool_timeout`, `database_pool_recycle` | `HyperAdminSettings` | `None` (SQLAlchemy's default) | [Connection pool](#connection-pool) |
| `database_pool_pre_ping` | `HyperAdminSettings` | `False` | [Connection pool](#connection-pool) |
| `rate_limit_requests`, `rate_limit_login_requests` | `HyperAdminSettings` | `None` (no limit) | [Rate limiting](#rate-limiting) |
| `rate_limit_window_seconds` | `HyperAdminSettings` | `60` | [Rate limiting](#rate-limiting) |
| `user_cache_ttl` | `HyperAdminSettings` | `0` (off) | [Permission checks](#permission-checks) |

Every `HyperAdminSettings` field can also be set as an environment variable with the
`HYPERADMIN_` prefix, for example `HYPERADMIN_DATABASE_POOL_SIZE=20`.

## SQLite or PostgreSQL

SQLite is fine for a demo, for tests and for an admin with one worker and few writers.
PostgreSQL is the choice for large tables and for several people working at once.

| | SQLite | PostgreSQL |
|---|---|---|
| Concurrent writes | One writer at a time; under concurrent writes it raises `database is locked` | Many writers |
| Workers | One | Several, each with its own connection pool |
| Row estimates (`count_estimate_threshold`) | None: every total is an exact count | Read from the planner statistics |
| Foreign-key size check (`preload_threshold`) | An exact `count(*)` of the related table | A catalog lookup, however large the table |
| Substring search | A table scan | A table scan, unless the column has a trigram index |
| Connection pool settings | Ignored for an in-memory database | Apply |

Measured figures for both, and the hardware they ran on, are on the
[Compatibility & Performance](../compatibility.md#performance) page: on SQLite a list page of a
100,000-row table took 112 ms, and on PostgreSQL the ERP example served about 300 requests per
second on 9 CPUs, with a median of 21 ms at 400 users.

### Indexes

HyperAdmin never creates an index; they belong in your migrations. Three kinds matter:

- **The sort column.** A list sorts by its first field (usually the primary key) until the user
  clicks a column header. Sorting by a column without an index sorts the whole table for every
  page. Cursor pagination needs the index too: it reads the next rows straight from it.
- **Foreign keys and filter columns.** PostgreSQL does not index a foreign-key column for you.
  Index the ones in `list_filter` and the ones a list is scoped by.
- **Search columns.** A B-tree index cannot serve `ILIKE '%term%'`. On PostgreSQL a trigram
  index can:

    ```sql
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX order_number_trgm ON "order" USING gin (number gin_trgm_ops);
    ```

## Connection pool

Under load, requests queue for a database connection once the pool is used up. SQLAlchemy's
default pool holds 5 connections plus 10 overflow, and a request waits 30 seconds for one before
it fails. When HyperAdmin builds the engine from `database_url`, set the pool through settings:

```python
from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings

settings = HyperAdminSettings(
    database_url="postgresql+asyncpg://admin:secret@db/app",
    database_pool_size=20,
    database_max_overflow=40,
    database_pool_timeout=30,
    database_pool_pre_ping=True,
)
admin = Admin(app, settings=settings)
```

When you pass your own engine, HyperAdmin leaves its pool alone, so build it with the same
arguments. `build_engine` drops the pool sizes for an in-memory SQLite URL, so one configuration
works in tests too:

```python
from hyperadmin.db import build_engine

engine = build_engine(
    DATABASE_URL,
    {"pool_size": 20, "max_overflow": 40, "pool_timeout": 30, "pool_pre_ping": True},
)
admin = Admin(app, engine=engine)
```

These values are a starting point, not a measured optimum. Each worker process has its own pool,
so keep `workers * (pool_size + max_overflow)` below PostgreSQL's `max_connections`: 4 workers
with the values above can open 240 connections. Start uvicorn with `--limit-concurrency` as well,
so a full worker answers 503 at once instead of queueing requests until the pool times out. The
[load-test notes](../compatibility.md#under-load) show what happened without it.

## Rate limiting

A traffic spike, or a script guessing passwords, goes straight to the database. HyperAdmin can
answer `429 Too Many Requests` with a `Retry-After` header once one client passes a limit. No
limit applies until you set one:

```python
settings = HyperAdminSettings(
    rate_limit_requests=300,  # admin requests per client per window
    rate_limit_login_requests=5,  # login form submissions per client per window
    rate_limit_window_seconds=60,
)
```

The limiter is a token bucket: a client may burst up to the limit and then sustains the average
rate. Static assets are never counted, and host routes outside the admin are not touched.

The built-in limiter counts per process, so with 3 workers a client gets up to 3 times the limit.
To enforce one limit across workers, pass your own limiter, backed by a store the workers share:

```python
from hyperadmin.core.rate_limit import RateLimitDecision


class SharedRateLimiter:
    async def acquire(self, key: str) -> RateLimitDecision:
        allowed, retry_after = await my_store.take_token(key)  # your shared counter
        return RateLimitDecision(allowed=allowed, retry_after=retry_after)


admin = Admin(app, engine=engine, rate_limiter=SharedRateLimiter())
```

Behind a reverse proxy the client address is the proxy's unless the server rewrites it: run
uvicorn with `--proxy-headers` and `--forwarded-allow-ips` set to your proxy. More detail is in
[Compatibility & Performance](../compatibility.md#rate-limiting).

## Measure your own data

`hyperadmin seed` fills a database with synthetic rows, including foreign keys with a realistic
skew, so you can try these options before your tables grow:

```bash
uv sync --extra loadtest
hyperadmin seed --plan erp --count 1000000 --database-url "$DATABASE_URL"
```

The built-in plans (`erp`, `auth`) fill the ERP example and the built-in user tables. They use
Faker, a development dependency, so run them from a checkout of the repository. For your own
schema, build a `SeedPlan` whose row factories return your columns and run it with
`hyperadmin.loadtest.BulkSeeder`. To measure under concurrent users, see
[Load testing your own deployment](../compatibility.md#load-testing-your-own-deployment).

## Relations on list pages

A list page loads only the relations it shows. Every relation named in `list_display`, either on
its own (`"customer"`) or through a dotted accessor (`"customer.name"`), is loaded with one
`SELECT ... IN (...)` for the page, whatever the page size. Other relations are not loaded, which
saves one query per relation on every request.

!!! note "Dotted accessors are loaded, not rendered"
    A dotted accessor such as `"customer.name"` loads the relation, but the list cell does not
    follow the dot yet and stays empty. Name the relation itself (`"customer"`) to show the
    related row's display name.

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(
        list_display=["number", "customer", "total"],  # loads "customer"
        list_select_related=["warehouse"],  # read by a custom list template
        detail_select_related=["customer", "lines"],  # the detail page loads only these
    )
```

| Option | Default | Effect |
|---|---|---|
| `list_select_related` | `None` | Extra relations to load on the list page. |
| `auto_select_related` | `True` | Load the relations named in `list_display`. `False` loads only `list_select_related`. |
| `detail_select_related` | `None` | Relations on the detail page. `None` loads every relation; `[]` loads none. |

!!! warning "Upgrading from 0.6"
    Before 0.7, a list page loaded every relation of the model. A custom list template, or a
    `__str__` that reads a relation, which is not in `list_display` now fails with
    `DetachedInstanceError`. Name the relation in `list_select_related`:

    ```python
    options = AdminOptions(list_select_related=["customer", "warehouse"])
    ```

    Detail pages are unchanged unless you set `detail_select_related`.

Adapters take the same list as a `load_relations` argument on `list()` and `get()`. An unknown
relation name raises `ValueError`.

## Search

The search box matches the typed text anywhere in a column, case-insensitively
(`ILIKE '%term%'`), and joins the columns with `OR`. Without `search_fields` it searches every
text column of the model except sensitive ones, so the cost grows with the number of rows times
the number of text columns.

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(search_fields=["number", "reference"])
```

| `search_fields` | Effect |
|---|---|
| `None` (default) | Search every non-sensitive text column. |
| `["number", "reference"]` | Search these columns only. |
| `[]` | No search for this model. |

On a large table, name one or two columns, and give them a trigram index on PostgreSQL (see
[Indexes](#indexes)). The command palette's record search (`palette_search=True`) uses the same
columns.

## List totals

The pager's total needs `count(*)`, which can take seconds on a table with millions of rows.

**Cache it.** With `count_cache_ttl` above zero, identical filters and search reuse the total for
that many seconds. Creating, updating or deleting a row of the model drops the cached totals.
Rows written by other processes show up once the TTL passes. The cache lives in each worker
process and keeps at most `count_cache_max_entries` totals (default 1024, set on
`HyperAdminSettings`), dropping the least recently used. A total is a few hundred bytes, so a full
cache is well under a megabyte per worker.

**Estimate it.** With `count_estimate_threshold` set, an unfiltered list of a table the database
estimates at that many rows or more skips the count and shows the estimate, marked with a tilde
(`of ~4200000 results`). On PostgreSQL the estimate is read from the planner statistics, so
`ANALYZE` keeps it fresh.

- Lists with a search or filter always count exactly.
- A table below the threshold counts exactly.
- A statistic of 0 or less (a table never analysed, or just bulk-loaded) counts exactly.
- SQLite and adapters that cannot estimate always count exactly.

The option is off by default so existing totals do not change. We recommend setting it to around
`1_000_000` on tables that large: the first page is the request that pays for the count most often,
and a few records of error do not matter at that size. The two options combine: the estimate
answers the unfiltered page, and the cache covers filtered ones.

```python
class EventAdmin(ModelAdmin):
    options = AdminOptions(count_cache_ttl=60, count_estimate_threshold=1_000_000)
```

## Deep pages

By default a list pages by number: page 5,000 of a list asks the database to read and discard
the 49,990 rows before it. `pagination_mode="cursor"` pages by key instead. Each page starts
after the last row of the previous one, by sort column and primary key, so every page costs the
same and no page counts the table.

```python
class EventAdmin(ModelAdmin):
    options = AdminOptions(pagination_mode="cursor")
```

| | `"offset"` (default) | `"cursor"` |
|---|---|---|
| Pager | Page numbers and a total | Previous and Next, no total |
| Cost of a deep page | Grows with the page number | Same as page 1 |
| `count(*)` per request | Yes (see [List totals](#list-totals)) | No |
| Link to a page | `?page=N` | `?cursor=...`; `?page=N` is ignored |

Search, filters and sorting work in both modes. Three things to know about cursor mode:

- **Index the sort column**, or each page still sorts the table (see [Indexes](#indexes)).
- **Some lists fall back to page numbers**, with a `KeysetFallbackWarning`: a model with a
  composite primary key, a sort on something that is not a mapped column, and a sort on a
  nullable column that holds NULLs among the listed rows.
- **It needs `SQLModelAdapter`.** Other adapters keep serving numbered pages and emit the same
  warning.

A cursor that was edited or cut short gets a `400` response.

## Foreign-key fields

A foreign key to a small table renders as a select with every option in the page. A foreign key
to a large table would make the form slow to load, so at `preload_threshold` rows (default 500)
the field becomes an autocomplete that fetches matches as the user types. The row count is the
same cheap estimate as above. Set `preload_threshold=None` to always preload, which is how 0.6
behaved. An adapter that cannot estimate keeps preloading.

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(preload_threshold=200)  # autocomplete from 200 related rows
```

## List filters

Each foreign-key filter in `list_filter` lists the first 50 rows of its related table, plus the
row that is currently applied. `filter_cache_ttl` (default 60 seconds, `0` to disable) reuses
those rows between renders and drops them when the related model is written through its adapter.
Rows written by other processes show up once the TTL passes.

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(list_filter=["customer", "status"], filter_cache_ttl=300)
```

A cached filter holds at most 50 choices, a few kilobytes, in the same per-worker cache as the
list totals, so `count_cache_max_entries` bounds both. Every worker process keeps its own copy.

## Permission checks

With the built-in `ModelPermissionChecker`, a request reads the signed-in user's direct and group
permissions once (two queries) and answers every check in that request from the result: the
sidebar, the route guard and the per-row actions. Superusers cost no permission query. Nothing is
kept between requests, so a grant or a revocation shows on the next one.

The set is remembered on the user object the auth backend returns for the request. Code that
changes permissions and then keeps checking the same user object should call
`hyperadmin.auth.permissions.forget_user_permissions(user)` first. To also skip the user and
permission queries on repeat requests, see `HYPERADMIN_USER_CACHE_TTL` (`user_cache_ttl`, default
`0`, at most 60 seconds) in
[Add HyperAdmin to an existing FastAPI app](existing-app.md#8-going-to-production).
