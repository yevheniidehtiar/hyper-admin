# SDD: Filter & Choice Scalability (FK preload threshold, filter cache)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #213 |
| Milestone | v0.7.0 — High-Volume & High-Load Scalability |
| Created | 2026-05-05 |
| Last updated | 2026-05-05 |

---

## Problem

Two long-standing defaults make HyperAdmin unusable on databases of even moderate size, well
before any "big data" thresholds are reached:

1. **`SelectFieldMeta.preload=True` is the default for FK columns** (see
   `src/hyperadmin/core/fields.py` line ~154 and `src/hyperadmin/core/choices.py` line ~35).
   Whenever a form contains a FK to a table with thousands of rows, the entire table is
   serialised into `<option>` tags inside a single `<select>`. With 50 000 rows this produces a
   ~2 MB HTML payload and locks the browser for several seconds; with 500 000 rows the page
   simply never finishes rendering. The HTMX autocomplete widget already exists (epic #159) and
   `RelationSelectWidget(preload=False)` already supports lazy loading
   (`src/hyperadmin/views/forms.py` lines 154–200) — but nothing decides *when* to use it.

2. **`build_filter_metadata()` re-fetches all FK reference rows on every list request.**
   `src/hyperadmin/core/discovery.py` line ~82 calls `target_adapter.list(page_size=1000)` for
   every FK field declared in `list_filter`, on every render of `list_view`
   (`src/hyperadmin/views/dynamic.py` line 221). A list page with three FK filters issues
   3 × `LIMIT 1000` queries against unrelated tables before the actual list query runs —
   independent of pagination, search, or filters. This metadata is effectively static and
   identical across users in a single process.

The combined effect is that HyperAdmin's perceived "slow page" cliff arrives at a few thousand
related rows rather than at any actual scalability bottleneck. Both fixes are local and
backwards-compatible if defaults are chosen carefully.

## Goals

- **Smart FK preload (C1).** No FK widget renders more than ~500 `<option>` tags by default.
  When a target table exceeds the configured threshold, the widget transparently downgrades to
  the existing HTMX autocomplete (`preload=False`) without any change to model definitions or
  templates.
- **Filter metadata cache (C2).** `build_filter_metadata()` for a given `(model, fields)` pair
  is fetched **at most once per TTL window** per process. With the default 60 s TTL, a model
  list page reloaded ten times in a minute issues zero extra FK reference queries after the
  first.
- **One shared cache utility.** A single `src/hyperadmin/core/cache.py` module provides the
  `cachetools.TTLCache` wrapper used by this epic and by epic #211 (adapter query
  performance), avoiding two near-identical caches in two different layers.
- **Operator opt-out is one keyword.** `AdminOptions(preload_threshold=None)` and
  `AdminOptions(filter_cache_ttl=0)` each restore pre-v0.7.0 behaviour exactly.
- **No new widgets, no template churn.** All UI changes go through code paths that already
  exist (`RelationSelectWidget(preload=False)` autocomplete, shipped in epic #159).

## Non-Goals

- **Per-user / per-tenant cache scoping.** Out of scope for v0.7.0; the filter metadata cache
  is process-global and identical for all users. Multi-tenant filter scoping waits until the
  multi-tenancy epic provides a `get_queryset()` seam for `build_filter_metadata`.
- **Distributed cache (Redis / memcached).** Per-process `cachetools.TTLCache` only;
  Redis-backed cache is deferred to v0.8 alongside other multi-worker primitives.
- **Search-server integration** (Elasticsearch / Meilisearch / Typesense) for FK autocomplete.
  Lives behind a separate adapter in a later milestone.
- **Query-level count caching** for `adapter.list()` / `adapter.count(filters=...)` — owned by
  epic #211 (story A3). This SDD only ships the table-wide `estimate_row_count()`.
- **Per-field `SelectFieldMeta.preload_threshold` override.** Model-wide
  `AdminOptions.preload_threshold` only in v0.7.0; per-field is a forward-compatible additive
  follow-up.
- **MySQL `estimate_row_count()` implementation.** Stub raises and falls back to preload — see
  Open Questions for the deferred work item.

## BDD Scenarios

Aggregated from the v0.7.0 stories under
`.meta/epics/epic-filter-choice-scalability-fk-preload-threshold-filter-c/stories/`. The story
files remain the canonical per-task spec; this section is the integration-level view.

```
Scenario: small FK target table preloads inline
  Given a model with an FK to a Country table containing 50 rows
  And   AdminOptions.preload_threshold = 500 (default)
  When  the create form is rendered
  Then  the response contains a <select> with 50 <option> tags
  And   no /choices/ HTMX endpoint is called

Scenario: large FK target table downgrades to HTMX autocomplete
  Given a model with an FK to a User table containing 50_000 rows
  And   AdminOptions.preload_threshold = 500 (default)
  When  the create form is rendered
  Then  the rendered widget is the lazy RelationSelectWidget (preload=False)
  And   the response contains zero <option> tags from the User table
  And   the widget has hx-get pointing at /<model>/choices/<rel>

Scenario: opt-out preserves pre-v0.7.0 behaviour
  Given a model with an FK to a User table containing 50_000 rows
  And   AdminOptions.preload_threshold = None
  When  the create form is rendered
  Then  all 50_000 users are emitted as <option> tags
  And   no estimate_row_count query is issued for the User table

Scenario: adapter without estimate_row_count falls back to preload
  Given a custom out-of-tree adapter that does not override estimate_row_count
  When  _build_relation_widgets resolves a relation widget for that adapter
  Then  estimate_row_count raises NotImplementedError
  And   the widget is built with preload=True (assume small)
  And   no exception propagates to the request handler

Scenario: filter metadata is cached within the TTL window
  Given AdminOptions.filter_cache_ttl = 60
  And   list_view has been rendered once for OrderAdmin
  When  list_view is rendered again 30 seconds later
  Then  build_filter_metadata is NOT called a second time
  And   the cached metadata is reused

Scenario: filter metadata is refreshed after TTL expiry
  Given AdminOptions.filter_cache_ttl = 60
  And   list_view has been rendered once for OrderAdmin
  When  list_view is rendered again 90 seconds later
  Then  build_filter_metadata is called a second time
  And   the cache entry is replaced

Scenario: filter cache disabled bypasses lookup entirely
  Given AdminOptions.filter_cache_ttl = 0
  When  list_view is rendered twice in succession
  Then  build_filter_metadata is called twice
  And   no entry is written to the TTL cache

Scenario: estimate_row_count never-analyzed Postgres table falls back to COUNT(*)
  Given a freshly created Postgres table with reltuples = -1
  When  estimate_row_count() is awaited on its adapter
  Then  the adapter executes SELECT COUNT(*) FROM <table>
  And   the returned value is the exact row count
```

## Design

### Architecture

```
                       ┌──────────────────────────────────────┐
                       │       core/cache.py    (NEW)         │
                       │  cachetools.TTLCache wrapper         │
                       │  - filter_metadata_cache (this SDD)  │
                       │  - count_cache           (epic #211) │
                       │  - clear_*() helpers                 │
                       └──────────┬───────────────────────────┘
                                  │ used by
                ┌─────────────────┴─────────────────────────┐
                │                                           │
                ▼                                           ▼
   ┌──────────────────────────────┐         ┌──────────────────────────────┐
   │   core/discovery.py          │         │   core/options.py            │
   │   build_filter_metadata()    │         │   AdminOptions               │
   │   wrapped with TTLCache      │         │   + preload_threshold: int|None│
   │   key=(model_qualname,       │         │   + filter_cache_ttl: int    │
   │        tuple(sorted(fields)))│         └──────────────────────────────┘
   └──────────────┬───────────────┘                       │
                  │ called by                             │ read by
                  ▼                                       ▼
       ┌──────────────────────────────────────────────────────────┐
       │                  views/dynamic.py                        │
       │  list_view → _get_filter_metadata (cached)               │
       │  _build_relation_widgets:                                │
       │    1. resolve target_adapter via adapter_registry        │
       │    2. count = await target_adapter.estimate_row_count()  │
       │       (per-request memo dict[model, int])                │
       │    3. if meta.preload and threshold and count >= threshold:│
       │           meta = replace(meta, preload=False)            │
       └──────────────────────────────────┬───────────────────────┘
                                          │ uses
                                          ▼
       ┌────────────────────────────────────────────────────────┐
       │                core/adapters.py                        │
       │  BaseAdapter.estimate_row_count() -> int               │
       │  default: raise NotImplementedError                    │
       └──────────────────────────────────┬─────────────────────┘
                                          │ overridden by
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
   adapters/sqlmodel.py        adapters/sqlalchemy.py        third-party adapters
   - Postgres: pg_class.       (mirrors sqlmodel impl)        (no override = fallback)
     reltuples (regclass)
     fallback COUNT(*) if -1
   - SQLite:  COUNT(*)
   - MySQL:   raise NotImpl
              (deferred)
```

The two stories within this epic are independent in the dependency graph — C1 and C2 touch
disjoint code paths and ship in either order. They share `core/cache.py` only via C2; C1 does
not require the cache at all (`estimate_row_count` is invoked once per relation per request).

### Data Model Changes

No data model changes. No migrations. `estimate_row_count` reads system catalogs
(`pg_class`) on Postgres and runs a plain `COUNT(*)` on SQLite — no application schema is
touched.

### API / Protocol Changes

#### `core/cache.py` (new module)

Single utility module shared with epic #211. Module-level singletons; no class hierarchy.

```python
# src/hyperadmin/core/cache.py
from __future__ import annotations

from typing import Any
from cachetools import TTLCache

# Filter metadata cache (this SDD). Default TTL=60s; AdminOptions.filter_cache_ttl
# overrides per-request via the wrapper helper, not by mutating the TTLCache.
_FILTER_METADATA_MAXSIZE = 128
filter_metadata_cache: TTLCache[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = TTLCache(
    maxsize=_FILTER_METADATA_MAXSIZE,
    ttl=60,
)

def clear_filter_metadata_cache() -> None:
    """Drop all cached filter metadata. Used by tests and admin tooling."""
    filter_metadata_cache.clear()

# Count cache slot reserved for epic #211 (adapter query performance / story A3).
# Declared here so the two epics share one module rather than duplicating wrappers.
```

The cache is a single module-level `TTLCache` instance. `cachetools.TTLCache` is not natively
asyncio-aware; we rely on `asyncio.run`'s single-threaded event-loop semantics — every cache
mutation happens inside the running coroutine on the loop's thread (no executor offload), so
no lock is required for one uvicorn worker. Multi-worker deployments get one cache per worker
(documented; pluggable backend deferred to v0.8).

#### `BaseAdapter.estimate_row_count()`

Distinct from epic #211's `BaseAdapter.count(filters=...)`. The two methods serve different
purposes and must not be confused:

| Method | Scope | Accuracy | Cost | Purpose |
|---|---|---|---|---|
| `estimate_row_count()` (this SDD) | whole table | approximate (planner stats) | O(1) | preload-vs-autocomplete decision |
| `count(filters=...)` (epic #211) | filtered query | exact | O(rows scanned) | pagination total |

```python
# src/hyperadmin/core/adapters.py
class BaseAdapter(ABC):
    ...
    async def estimate_row_count(self) -> int:
        """Return an approximate row count for ``self.model``'s underlying table.

        Used to decide whether an FK widget should preload all options or fall back
        to lazy HTMX autocomplete. Implementations should prefer cheap planner
        statistics (e.g. PostgreSQL ``pg_class.reltuples``) over a real ``COUNT(*)``,
        and may return -1 or raise :class:`NotImplementedError` when no estimate is
        available.

        The default implementation raises :class:`NotImplementedError` so that
        third-party adapters that do not override it preserve pre-v0.7.0 behaviour
        (the view layer falls back to ``preload=True``).

        Returns:
            An approximate, non-negative row count. Callers must treat the value as
            advisory only and not depend on exactness.
        """
        raise NotImplementedError
```

##### Postgres implementation (`adapters/sqlmodel.py`, mirrored in `adapters/sqlalchemy.py`)

```python
async def estimate_row_count(self) -> int:
    table = self.model.__tablename__
    async with self.engine.connect() as conn:
        # Use parameterized regclass cast — never f-string the table name into SQL.
        result = await conn.execute(
            text("SELECT reltuples::bigint FROM pg_class WHERE oid = :tbl::regclass"),
            {"tbl": table},
        )
        row = result.scalar_one_or_none()
        if row is None or row < 0:
            # reltuples = -1 on never-analyzed tables; fall back to exact count.
            result = await conn.execute(text(f"SELECT COUNT(*) FROM {quoted(table)}"))
            return int(result.scalar_one())
        return int(row)
```

The `quoted(table)` step uses SQLAlchemy's `Identifier`-equivalent quoting via
`sa.sql.quoted_name(table, quote=True)` — never raw f-string interpolation. SQLite uses a
plain `SELECT COUNT(*)` (it has no row-estimate catalog and reference tables on SQLite are
small enough that the linear scan is acceptable for dev workflows). MySQL is deliberately not
implemented: the default `NotImplementedError` triggers the safe-preload fallback for any
deployment we do not yet support.

#### `_build_relation_widgets` integration

```python
# src/hyperadmin/views/dynamic.py
async def _build_relation_widgets(
    self,
    field_names: list[str],
    selected_values: dict[str, Any] | None = None,
) -> dict[str, HtmxWidget]:
    threshold = self.options.preload_threshold  # int | None
    row_count_memo: dict[type, int | None] = {}  # per-request cache
    ...
    for name, field_info in self.model.model_fields.items():
        ...
        if meta.preload and threshold is not None:
            target_model = _resolve_target_model(self.model, name)  # via mapper
            if target_model is not None:
                count = row_count_memo.get(target_model, _SENTINEL)
                if count is _SENTINEL:
                    target_adapter_cls = adapter_registry.find_adapter_for_model(target_model)
                    target_adapter = target_adapter_cls(target_model, self.adapter.engine)
                    try:
                        count = await target_adapter.estimate_row_count()
                    except NotImplementedError:
                        count = None
                    row_count_memo[target_model] = count
                if count is not None and count >= threshold:
                    meta = replace(meta, preload=False)
        ...
```

Memoising per request keeps `_build_relation_widgets` O(distinct relation targets) for the
estimate call rather than O(fields), which matters for forms with many FKs to the same model.

#### `build_filter_metadata` cache wrapper

```python
# src/hyperadmin/core/discovery.py
async def build_filter_metadata(
    model: Any,
    field_names: list[str],
    adapter: Any,
    *,
    cache_ttl: int = 60,
) -> list[dict[str, Any]]:
    if cache_ttl == 0:
        return await _build_filter_metadata_uncached(model, field_names, adapter)

    key = (f"{model.__module__}.{model.__qualname__}", tuple(sorted(field_names)))
    cached = filter_metadata_cache.get(key)
    if cached is not None:
        return cached
    metadata = await _build_filter_metadata_uncached(model, field_names, adapter)
    filter_metadata_cache[key] = metadata
    return metadata
```

The signature gains a single keyword-only `cache_ttl` argument; the body of the original
function is renamed to `_build_filter_metadata_uncached`. Callers in `views/dynamic.py` pass
`self.options.filter_cache_ttl`. `cache_ttl=0` short-circuits both the cache lookup and the
write — no entry is created, no TTL fires, the call behaves exactly like pre-v0.7.0.

Cache key choice (`model_qualname`, `tuple(sorted(field_names))`) intentionally **does not**
include request-scoped state (user, query params, session). The metadata is the same for all
users — every FK target list is fetched up to 1000 rows regardless of caller — so per-user
keys would only fragment the cache. When multi-tenant filter scoping arrives, this key
becomes `(model_qualname, fields, tenant_id)` via a project-supplied scope function; the
extension is additive.

### Configuration Changes

Two new fields on `AdminOptions`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `preload_threshold` | `int \| None` | `500` | If a relation target table has at least this many rows, the FK widget switches from preload to lazy HTMX. `None` disables the auto-downgrade and preserves pre-v0.7.0 behaviour. Units = rows. |
| `filter_cache_ttl` | `int` | `60` | Seconds to cache `build_filter_metadata` output per `(model, fields)`. `0` disables the cache (lookup is skipped entirely — short-circuit). |

Per-`SelectFieldMeta` overrides (`preload_threshold` per field) are deliberately deferred —
the field already has `preload: bool`, and a later release can extend it with
`preload_threshold: int | None = None` (additive, no BC break).

`pyproject.toml` gains one runtime dependency:

```toml
dependencies = [
  ...
  "cachetools>=5",
]
```

`cachetools>=5` is a tiny pure-Python package (~30 KB) with no transitive deps; the lower
bound matches the API used (`TTLCache.maxsize`, `TTLCache.ttl`).

### Tests

- **Unit:**
  - `tests/unit/test_estimate_row_count.py` — Postgres `reltuples`, never-analyzed fallback,
    SQLite count, MySQL stub, `BaseAdapter` raises by default.
  - `tests/unit/test_preload_threshold.py` — small/large/opt-out paths, per-request memo,
    fallback to preload on `NotImplementedError`.
  - `tests/unit/test_filter_metadata_cache.py` — cache hit within TTL, refresh after TTL,
    `cache_ttl=0` skip path, key = `(qualname, sorted_fields)`, `clear_filter_metadata_cache`.
- **E2E:** `tests/e2e/test_fk_preload_threshold.py` — large FK renders autocomplete; small FK
  renders inline `<select>`; `data-testid` selectors only; opt-out scenario.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Postgres `reltuples = -1` (never analyzed) | Fallback to exact `SELECT COUNT(*)` once; result returned as the estimate. Cost is bounded because this only happens on tables that have never been written to. |
| `pg_class` regclass cast failure (table dropped, schema mismatch) | `NotImplementedError`-equivalent — the `_build_relation_widgets` try/except path treats it as "estimate unavailable" and keeps `preload=True`. Logs a warning. |
| Table name with mixed case / quoted identifier | Use SQLAlchemy `quoted_name(..., quote=True)` for the COUNT(*) fallback; the `:tbl::regclass` parameterised cast handles the lookup correctly. Never f-string `__tablename__` into SQL. |
| Multi-tenant `get_queryset` filters not applied to filter metadata | **Known limitation.** `build_filter_metadata` fetches up to 1000 of every FK target globally, ignoring the caller's `get_queryset` scope. Tracked for the multi-tenancy epic; documented in the changelog and adapter docstring. Practical impact in v0.7.0: a tenant-scoped filter dropdown may show options the user cannot actually filter to. Mitigation today: set `list_filter=[]` on tenant-scoped models. |
| Adapter without `estimate_row_count` (out-of-tree custom adapter) | Default `BaseAdapter.estimate_row_count` raises `NotImplementedError`. View catches and treats the relation as "assume small" → `preload=True`. Behaviour is identical to v0.6.x for these adapters. |
| `preload_threshold=None` set globally | Skip the `estimate_row_count` call entirely (zero-overhead opt-out). Existing `preload` defaults are honoured. |
| `filter_cache_ttl=0` | Short-circuit both the cache lookup and write; no entry is created and nothing expires. Behaviour identical to v0.6.x. |
| TTLCache thread-safety in async context | `cachetools.TTLCache` is not lock-free, but a single uvicorn worker runs one event loop on one thread, and all cache mutations happen on coroutine resumption (no `run_in_executor`). Single-worker deployments are safe; multi-worker deployments get one cache per worker (acceptable — staleness window already ≤ TTL). |
| Cache key collision across module reloads / hot reload | Key includes `model.__module__ + model.__qualname__`, so a reload that produces a fresh class object generates a fresh key automatically. Stale entries from the previous class age out within TTL. |
| Mutations to FK reference tables during a TTL window | **Not invalidated.** Staleness is bounded by `filter_cache_ttl` (default 60 s). Documented; mutation-driven invalidation deferred (see Decision Log). |
| `find_adapter_for_model` returns `None` for the relation target | Treat as "estimate unavailable" → keep `preload=True`. Already the contract followed by `discovery.py`. |
| Concurrent first writes to the cache (cold cache, two requests in parallel) | Both compute and both write the same value; last-writer-wins. Outcome is correct, cost is one redundant query per cold start. Acceptable. |

## Migration & Backward Compatibility

- **One behavioural default changes.** With `preload_threshold=500` (the new default), an FK
  to a table with ≥ 500 rows now renders as an HTMX autocomplete widget instead of a giant
  `<select>`. The autocomplete widget already shipped in epic #159 (v0.4.x) — this SDD only
  reaches it via the threshold logic. UI styling, DOM structure, and data-testid IDs of the
  autocomplete are unchanged.
- **Opt-out is one keyword.** `AdminOptions(preload_threshold=None)` restores pre-v0.7.0
  behaviour exactly. Documented prominently in the v0.7.0 CHANGELOG.
- **No DB migration.** No new columns, no new tables, no new indexes.
- **No public API removals or renames.** `__init__.py` exports gain no new symbols (the cache
  utility is private to `core/`). The new `BaseAdapter.estimate_row_count` lands with a
  default that raises `NotImplementedError`, so out-of-tree adapters keep working — the view
  layer detects the exception and falls back to today's preload behaviour.
- **`cachetools` becomes a runtime dependency.** Single new dep, ~30 KB, pure-Python, zero
  transitive deps. Lower bound `>=5` matches the API used.
- **`SelectFieldMeta.preload` default stays `True`.** No widget defaults change. The
  threshold logic operates *over* `meta.preload` and only narrows it from `True` to `False`
  when warranted; widgets that opt into `preload=False` directly are untouched.
- **No semver-major bump.** Behaviour change is opt-out and additive; everything else is
  additive. Targeted at the v0.7.0 minor release.

## Open Questions

- [ ] **MySQL `estimate_row_count` implementation.** `information_schema.TABLES.TABLE_ROWS`
      is the obvious source on MySQL/MariaDB but is famously inaccurate on InnoDB (off by
      orders of magnitude on busy tables). Two options:
      (a) ship the InnoDB approximation now with a documented caveat; or
      (b) leave the stub raising `NotImplementedError` and file a follow-up.
      **Proposal:** (b) — defer until a concrete user reports needing it, since the safe
      fallback (assume small, preload) preserves correctness.
- [ ] **`filter_cache_ttl=0` semantics: short-circuit vs immediate-expire?** Current proposal
      is short-circuit (skip lookup and write entirely). Alternative is to set TTL=0 on the
      cache and rely on `cachetools`' eviction. Short-circuit is preferable: it is one fewer
      hash op, makes the disabled path obviously zero-overhead, and prevents the cache from
      ever holding entries an operator believes are disabled. **Proposal:** short-circuit.
- [ ] **Should `filter_cache_ttl` also gate per-relation FK option fetches?**
      `build_filter_metadata` itself calls `target_adapter.list(page_size=1000)` per FK; the
      proposed cache wraps the *outer* function so all FK fetches are amortised together. A
      finer-grained cache (per FK target) would help models that share FK targets across
      filters. **Proposal:** ship the outer cache only; revisit if profiling shows benefit.

These must be settled (or explicitly deferred) before Status → Approved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| New module `src/hyperadmin/core/cache.py` owned by this SDD, shared with epic #211 | Avoids two near-identical TTLCache wrappers in two layers; single place to evolve cache semantics (Redis backend, instrumentation). Decided here so #211 (count cache) plugs in additively. | Per-feature cache modules (more duplication, two test fixtures, two docs sections) |
| `cachetools>=5` as a runtime dep | ~30 KB pure-Python, zero transitive deps, battle-tested `TTLCache` with the exact semantics needed. Writing our own TTL eviction is gratuitous. | Hand-rolled `dict` + monotonic timestamps (more code, more bugs); `functools.lru_cache` (no TTL) |
| `AdminOptions.preload_threshold: int \| None = 500`, model-wide only | Single dial covers the 95% case (form-wide policy). Per-field override is purely additive on `SelectFieldMeta` and can land later without a BC break. | Per-field `SelectFieldMeta.preload_threshold` (more surface, no concrete user need today); global `HyperAdminSettings` knob (too coarse, hard to opt model in/out) |
| Default threshold = 500 | 500 `<option>` tags is roughly the upper bound of "still snappy" in modern browsers; below it, preload is faster than the HTMX round-trip. Conservative enough to be safe; tight enough to actually fire on the problem cases. | 100 (too aggressive — common FK tables hit it); 1000 (matches the page_size cap but doesn't actually solve the slow-page problem) |
| `BaseAdapter.estimate_row_count()` default raises `NotImplementedError` | Out-of-tree adapters that pre-date v0.7.0 keep working unchanged (view layer catches and falls back to preload). Forces tree adapters to opt in. | Default returning `0` (would silently force everyone into autocomplete); abstract method (would break existing custom adapters on upgrade) |
| Postgres impl uses `pg_class.reltuples` with `:tbl::regclass` parameterised cast | O(1), no table scan, accurate enough for the threshold decision. Parameterised regclass cast eliminates SQL injection from `__tablename__`. Fallback to `COUNT(*)` only when `reltuples = -1` (never analyzed) preserves correctness on fresh tables. | `COUNT(*)` always (defeats the optimisation); `pg_stat_user_tables.n_live_tup` (similar but requires stats collector to be running, less universally available) |
| `estimate_row_count` is distinct from epic #211's `count(filters=...)` | Different scope (whole table vs filtered query), different accuracy (approximate vs exact), different cost (O(1) vs O(rows)). Conflating them would either force exact counts here (slow) or approximate counts there (incorrect pagination). | Single `count()` method (rejected — semantics conflict) |
| Filter metadata cache key = `(model_qualname, tuple(sorted(field_names)))` | `build_filter_metadata` does not vary on user, query params, or filters today — every render fetches up to 1000 of every FK target globally. Per-user keys would only fragment the cache without changing output. Sorted field names normalise call ordering. | Include user/tenant in the key (no current variance, would be cache pollution); include query params (same — no variance) |
| Time-based invalidation only; no mutation hooks | Mutation-driven invalidation requires hooking every adapter `create`/`update`/`delete` for every FK target — a significant invasion for a 60 s staleness window that is already shorter than typical reference-data churn. Operators who need fresher data set `filter_cache_ttl` lower. | Hook into adapter mutations to evict (more complex, leaks coupling between adapter and discovery); event-bus (out of scope) |
| Per-process cache (one `TTLCache` per uvicorn worker) | Single-worker deployments are unaffected; multi-worker deployments get N independent caches with bounded staleness ≤ TTL — same correctness guarantee, just more redundant queries on cold start. Distributed cache is a v0.8 concern alongside other shared-state primitives. | Redis-backed cache (out of scope; deferred); inter-process shared memory (operationally heavy, brittle on restart) |
| `filter_cache_ttl=0` short-circuits the lookup | Operationally clearest semantics: "0 = off, no entries created, no TTL ever fires". One hash op cheaper than the `TTL=0` eviction path. | Set TTL to 0 on the underlying cache (entries created and immediately evicted — same end result, more code paths) |
| Per-request `dict[model, int]` memo for `estimate_row_count` in `_build_relation_widgets` | Forms with multiple FKs to the same target (e.g. two `created_by` / `updated_by` user FKs) issue one estimate call rather than N. Per-request scope avoids cross-request leakage. | No memo (re-issues the catalog query per FK — cheap on Postgres but not free); module-level cache for `estimate_row_count` (longer staleness, harder to test) |
| MySQL impl deferred (raise) | Safe fallback (assume small, preload) preserves correctness; no current user has reported needing it; `information_schema.TABLES.TABLE_ROWS` is famously inaccurate on InnoDB and would need a tunable fallback. | Ship a best-effort impl now (more surface, more edge cases, no concrete demand) |
