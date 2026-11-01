# SDD: Adapter Query Performance (selectinload, pagination, count, search)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | In Review |
| Issue | #211 |
| Milestone | v0.7.0 — High-Volume & High-Load Scalability |
| Created | 2026-05-05 |
| Last updated | 2026-11-01 |

---

## Problem

HyperAdmin's adapter layer (`SQLModelAdapter`, `SQLAlchemyAdapter`) was designed for ergonomics
on small/medium datasets and degrades sharply on production-sized tables. The v0.7.0 milestone
("High-Volume & High-Load Scalability") commits HyperAdmin to working on **10M-row** tables
under realistic load. Today, four named bottlenecks block that goal:

1. **Unconditional `selectinload` on every relation.** `SQLModelAdapter.list()` walks
   `mapper.relationships` and adds a `selectinload()` for each one (`adapters/sqlmodel.py:71-72`).
   On a model with 5 FKs / collections that is **5 extra SELECTs per list request** — every page
   load — regardless of which relations the table actually displays. There is no opt-out.
2. **OFFSET-based pagination.** Both adapters use `query.offset((page - 1) * page_size).limit(...)`.
   At `OFFSET 10_000_000` the database scans 10M rows before returning the page — a linear
   degradation that no index can fix. Deep pagination is effectively unusable.
3. **`COUNT(*)` on every list request, never cached.** Both adapters issue a separate
   `select(func.count())` alongside every list query. On a 10M-row table with non-trivial
   `WHERE` predicates this costs seconds **per request** and dominates the p99 latency.
4. **`ILIKE '%search%'` on heuristically-detected string columns.** `SQLAlchemyAdapter.list()`
   currently **silently ignores the `search_fields` parameter** (`# noqa: ARG002`,
   `adapters/sqlalchemy.py:51`) and unconditionally `ILIKE`s every `String`/`AutoString` column
   on the model. On a wide table this means full-table scans across columns the operator never
   intended to be searchable. `SQLModelAdapter` honours `search_fields` but its default
   heuristic has the same shape.

`AdminOptions.search_fields` already exists as a config field but only one adapter consumes it.
There is no way to disable eager relation loading, no caching seam for COUNT, and no cursor /
keyset pagination support. v0.7.0 cannot meet its load-testing acceptance criteria
(`epic-locust-load-testing-suite-100-reqs-against-10m-records`) without these four fixes.

## Goals

- **A1 — Configurable selectinload.** Default list views to **load nothing** (no
  `selectinload`); reduce list-view query count by **at least 5 SELECTs per request** on
  models with 5+ relations. Provide explicit opt-in (`list_select_related: list[str]`) and an
  opt-in helper (`auto_select_related=True`) that auto-derives needed relations from
  `column_list`. Detail view keeps current auto-detect behaviour for backward compatibility.
- **A2 — Configurable search_fields parity.** `SQLAlchemyAdapter.list()` honours the
  `search_fields` argument identically to `SQLModelAdapter`. When unset, both adapters fall
  back to the same heuristic (string columns excluding the primary key) so users get
  predictable, declarable search scope.
- **A3 — Opt-in COUNT cache.** Pluggable `CountCache` Protocol in `core/cache.py`. Default
  in-memory TTL implementation ships in v0.7.0. Cache key is `(model_qualname, filters,
  search, queryset_filters)` — explicitly excludes pagination/order. With a 30-second TTL on a
  10M-row dataset, COUNT(*) load drops by **>95%** at sustained 100 req/s.
- **A4 — Keyset (cursor) pagination.** Opt-in `pagination_mode="cursor"` on `AdminOptions`.
  Provides **O(log N)** pagination via index seek on `(sort_col, pk)` regardless of depth.
  Returns opaque base64-urlsafe cursors; falls back to OFFSET when sort target is
  non-deterministic.

All goals are individually deliverable and pairwise composable.

## Non-Goals

- **Full-text search backends.** `tsvector` (PostgreSQL), MeiliSearch, Typesense, Elastic — all
  out of scope. A2 only fixes the existing `ILIKE` parity gap.
- **Distributed cache backend.** `RedisCountCache` is **deferred to v0.8**. The protocol is
  declared in v0.7.0 so a Redis impl can ship without an SDD revision; only the in-memory
  backend ships now.
- **Detail-view selectinload default change.** Detail views keep the current auto-detect
  behaviour. Changing them risks breaking `__str__` rendering on FK-referenced rows; that
  is a separate, BC-sensitive design conversation.
- **Adapter CRUD redesign.** `create()`, `update()`, `delete()`, `get_choices()`,
  `save_inline_rows()` are untouched.
- **Schema migrations.** No DB schema changes — every change is in adapter / view / template
  code or in-memory caches.
- **Replacing `BaseAdapter.list()` signature.** This SDD adds `list_paginated()` alongside
  `list()` and deprecates the latter; signature collapse is deferred to v1.0.
- **Computing the estimate.** `BaseAdapter.estimate_row_count()` (PG `pg_class.reltuples`) is
  owned by the sibling epic (filter-choice scalability). A3 here only *consumes* it for the
  unfiltered list total (see "A3 — estimated total" below); every filtered count stays
  exact-but-cached.

## BDD Scenarios

Aggregated from stories under
`.meta/epics/epic-adapter-query-performance-selectinload-pagination-count/stories/`. Per-story
scenarios remain canonical; this section is the integration-level view used by the
implementation sub-tasks.

### A1 — Configurable selectinload (#215, #216, #217, #218)

```
Scenario: list view with default options issues no relation SELECTs
  Given a Product model with 5 relations and AdminOptions(list_select_related=None)
  When  GET /admin/product is rendered with 10 rows
  Then  exactly one SELECT against product is issued
  And   no SELECT against any relation table is issued

Scenario: list_select_related explicitly loads named relations
  Given AdminOptions(list_select_related=["category", "vendor"])
  When  the adapter list() is called
  Then  selectinload is applied for "category" and "vendor"
  And   no selectinload is applied for any other relation

Scenario: auto_select_related derives relations from column_list
  Given AdminOptions(column_list=["name", "category.name"], auto_select_related=True)
  When  the adapter list() is called
  Then  selectinload is applied for "category"
  And   no other relation is loaded

Scenario: detail view preserves auto-detect (backward compatible)
  Given AdminOptions(detail_select_related=None)
  When  GET /admin/product/42 is rendered
  Then  FK relations referenced by __str__ rendering are eagerly loaded
  And   the rendered template raises no DetachedInstanceError
```

### A2 — Configurable search_fields (#219, #220, #221, #222)

```
Scenario: SQLAlchemyAdapter honours search_fields when set
  Given a User model with columns (name, email, bio) and search_fields=["name", "email"]
  When  adapter.list(search="alice") is called
  Then  the WHERE clause ILIKEs name AND email
  And   the WHERE clause does NOT ILIKE bio

Scenario: search_fields=None uses string-columns-minus-pk heuristic
  Given a User model and search_fields=None on AdminOptions
  When  adapter.list(search="alice") is called
  Then  every string column except the primary key participates in the ILIKE OR-chain

Scenario: search_fields=[] disables search entirely
  Given AdminOptions(search_fields=[])
  When  adapter.list(search="alice") is called
  Then  no ILIKE predicate is added to the WHERE clause
  And   the search box renders as disabled in the list view
```

### A3 — COUNT cache (#223, #224, #225)

```
Scenario: count_cache_ttl=0 disables caching (BC default)
  Given AdminOptions() with count_cache_ttl=0
  When  two consecutive list requests with identical filters arrive
  Then  the database receives two COUNT(*) queries

Scenario: cache hit within TTL serves total without DB round trip
  Given AdminOptions(count_cache_ttl=30)
  And   a previous list() populated the cache 5 seconds ago
  When  list() is called again with identical filters/search/queryset_filters
  Then  no COUNT(*) query is issued
  And   the cached total is returned

Scenario: cache miss on differing filters issues a fresh COUNT
  Given a populated cache for filters={"status": "active"}
  When  list() is called with filters={"status": "archived"}
  Then  a COUNT(*) query is issued for the new filter set

Scenario: create/update/delete invalidates the model's count cache
  Given a populated cache for the Product model
  When  adapter.create({...}) is called
  Then  all cache entries scoped to Product are evicted
  And   the next list() issues a fresh COUNT(*)

Scenario: a large unfiltered table uses the estimate instead of COUNT(*)
  Given AdminOptions(count_estimate_threshold=1_000_000)
  And   estimate_row_count() returns 4_200_000
  When  list() is called with no search, filters or queryset_filters
  Then  no COUNT(*) query is issued
  And   the result has total=4_200_000 and total_is_estimate=True

Scenario: a filtered list always uses the exact count
  Given the same options and estimate
  When  list() is called with search="tomato"
  Then  an exact COUNT(*) is issued for the filtered query
  And   total_is_estimate is False

Scenario: a table below the threshold stays exact
  Given count_estimate_threshold=1_000_000 and estimate_row_count() returns 12_000
  When  list() is called with no filters
  Then  an exact COUNT(*) is issued

Scenario: an adapter that cannot estimate falls back to the exact count
  Given count_estimate_threshold is set and estimate_row_count() returns None
  When  list() is called with no filters
  Then  an exact (cached) COUNT(*) is issued
```

### A4 — Keyset cursor pagination (#226, #227, #228, #229, #230)

```
Scenario: pagination_mode="offset" preserves current behaviour
  Given AdminOptions(pagination_mode="offset")
  When  list() is called with page=2, page_size=10
  Then  the SQL uses OFFSET 10 LIMIT 10
  And   the response includes total

Scenario: pagination_mode="cursor" uses keyset on (sort_col, pk)
  Given AdminOptions(pagination_mode="cursor") and order_by="-created_at"
  When  list_paginated(cursor=None, page_size=10) is called
  Then  no OFFSET is used
  And   the WHERE clause is "(created_at, id) < (sentinel, sentinel) ORDER BY created_at DESC, id DESC LIMIT 11"
  And   the response includes next_cursor and has_next

Scenario: cursor decodes to (pk, sort_col, direction)
  Given a previous response returned next_cursor="eyJrIjpbNDIs..."
  When  list_paginated(cursor=next_cursor, page_size=10) is called
  Then  the WHERE clause filters rows after the cursor's (sort_col, pk) tuple
  And   results follow the previous page contiguously

Scenario: cursor mode returns total=None
  Given AdminOptions(pagination_mode="cursor")
  When  list_paginated() is called
  Then  the ListResult.total field is None
  And   the template hides the "X of Y" label
  And   prev/next links use cursors instead of page numbers

Scenario: cursor mode falls back to offset when sort is non-deterministic
  Given AdminOptions(pagination_mode="cursor") and no explicit sort
  And   the model has no obvious deterministic order
  When  list_paginated() is called
  Then  the adapter logs a warning
  And   it transparently uses OFFSET pagination

Scenario: invalid/tampered cursor returns 400
  Given a malformed cursor "not-base64"
  When  GET /admin/product?cursor=not-base64
  Then  the response is 400 with "Invalid pagination cursor"
```

## Design

### Architecture

```
                       ┌─────────────────────────────────────┐
                       │         core/cache.py (NEW)         │
                       │   CountCache Protocol               │
                       │   InMemoryTTLCache (default impl)   │
                       │   (shared with epic #213 SDD —      │
                       │    filter-choice-scalability.md)    │
                       └─────────────────────────────────────┘
                                       ▲
                                       │ injected into adapters
                                       │ via AdminOptions
                                       │
   ┌──────────────────┐    ┌───────────┴──────────────────┐
   │ core/options.py  │    │       core/adapters.py       │
   │ + list_select_   │    │  ListResult dataclass        │
   │   related        │────► CursorCodec helpers          │
   │ + detail_select_ │    │ + list_paginated()  (NEW)    │
   │   related        │    │   list() (DEPRECATED tuple)  │
   │ + auto_select_   │    │  estimate_row_count()        │
   │   related        │    │   (epic #213, sibling)       │
   │ + search_fields  │    └──────────────┬───────────────┘
   │   (existing)     │                   │
   │ + count_cache_   │                   │ implements
   │   ttl            │                   │
   │ + pagination_    │                   ▼
   │   mode           │    ┌──────────────────────────────┐
   └──────────┬───────┘    │ adapters/sqlmodel.py         │
              │            │ adapters/sqlalchemy.py       │
              │ consumed   │  (A1) opt-in selectinload    │
              ▼            │  (A2) honour search_fields   │
   ┌──────────────────┐    │  (A3) wrap COUNT in cache    │
   │ views/dynamic.py │    │  (A4) keyset SQL builder     │
   │ list_view:       │    └──────────────┬───────────────┘
   │  - calls         │                   │ produces
   │    list_paginated│                   ▼
   │  - decodes       │    ┌──────────────────────────────┐
   │    cursor query  │    │ templates/components/        │
   │    param         │    │   table.html                 │
   │  - passes        │◄───│   pagination.html  (UPDATED) │
   │    select_related│    │   - cursor links when        │
   └──────────────────┘    │     ListResult.total is None │
                           │   - page links otherwise     │
                           └──────────────────────────────┘
```

The change spans 4 modules (`core/`, `adapters/`, `views/`, `templates/`) but each work item
A1-A4 layers cleanly on top of the previous one. Implementation order matches the planning
playbook: `core` → adapters → views → templates.

#### Relationship to sibling SDDs

| SDD | Owns | Shared surface |
|---|---|---|
| `adapter-query-performance.md` (this) | `BaseAdapter.list_paginated()`, `count(filters)` (cached, exact), `CountCache` protocol consumer | `core/cache.py` |
| `filter-choice-scalability.md` (epic #213) | `BaseAdapter.estimate_row_count()` (approximate, no filters), `core/cache.py` module ownership | `core/cache.py` |

`count()` (this SDD) and `estimate_row_count()` (#213 SDD) are intentionally **two different
methods** — exact-with-filters vs approximate-without-filters — so callers pick the right
trade-off explicitly. They coexist on the protocol.

### Data Model Changes

No data model changes. Every change is in adapter / view / template code or in-memory caches.

### API / Protocol Changes

#### A1 — Configurable selectinload

`BaseAdapter.list()` and the new `BaseAdapter.list_paginated()` (see A4) accept
`load_relations: list[str] | None = None`:

```python
# core/adapters.py
async def list_paginated(
    self,
    *,
    page: int = 1,
    page_size: int = 10,
    cursor: str | None = None,
    search: str | None = None,
    filters: dict[str, Any] | None = None,
    order_by: str | None = None,
    search_fields: list[str] | None = None,
    load_relations: list[str] | None = None,
) -> ListResult: ...
```

Adapter behaviour:

- `load_relations is None` → **no** `selectinload`. (BREAKING for list path.)
- `load_relations == []` → no `selectinload` (explicit form of the same).
- `load_relations == ["category", "vendor"]` → `selectinload(Model.category)`,
  `selectinload(Model.vendor)`. Unknown relation names raise `ValueError`.

Detail (`get()`) keeps current behaviour — auto-detects FK relations needed by `__str__`
rendering — controlled separately by `detail_select_related` (semantics: `None` = auto-detect,
`[]` = none, `[...]` = explicit).

`auto_select_related=True` on `AdminOptions` makes the view layer derive `load_relations` from
`column_list` entries containing `.` (relation accessors, e.g. `"category.name"` →
`load_relations=["category"]`).

#### A2 — Configurable search_fields

No protocol change — `search_fields` already lives on `BaseAdapter.list()`. The fix is in
`SQLAlchemyAdapter.list()` only:

```python
# adapters/sqlalchemy.py — replace silent ignore
if search:
    fields = search_fields if search_fields is not None else self._default_search_fields()
    if fields:
        clauses = [getattr(self.model, f).ilike(f"%{search}%") for f in fields]
        where_conditions.append(or_(*clauses))
```

`_default_search_fields()` returns string columns excluding PK (matches `SQLModelAdapter._detect_search_fields()` — share the implementation via a small mixin in `adapters/_search.py`).

#### A3 — COUNT cache

New module `src/hyperadmin/core/cache.py` (shared with epic #213):

```python
@runtime_checkable
class CountCache(Protocol):
    async def get(self, key: tuple) -> int | None: ...
    async def set(self, key: tuple, value: int, ttl: int) -> None: ...
    async def invalidate_model(self, model_qualname: str) -> None: ...

class InMemoryTTLCache:  # ships in v0.7.0
    def __init__(self, max_entries: int = 1024) -> None: ...
    # implements CountCache

# RedisCountCache — declared, NOT shipped in v0.7.0 (deferred to v0.8)
```

**Cache key shape:**
```python
key = (
    model_qualname,                            # str
    frozenset((filters or {}).items()),        # frozenset of (col, value)
    search or "",                              # str — empty string when unset
    frozenset(queryset_filters.items()),       # RLS / tenant filters
)
```
`page`, `page_size`, `order_by`, `cursor` are **excluded** — they don't affect the count.
Frozensets require all values to be hashable; non-hashable filter values bypass cache and
log a debug message.

`BaseAdapter.count(filters=...)` (existing internal — promoted to public) consults the cache
when `count_cache_ttl > 0`. Adapters call `cache.invalidate_model(self.model.__qualname__)`
inside `create()`, `update()`, `delete()`. A `BaseAdapter.invalidate_count_cache()` hook lets
applications clear manually after bulk operations they performed outside the adapter.

##### A3 — estimated total for unfiltered lists (added 2026-11-01)

Scale tests on 1M and 10M-row tables showed the default list page (no search, no filter) costs
one multi-second `count(*)` on large tables, even when the page query itself is fast. A TTL
cache only helps from the second hit. When `count_estimate_threshold` is set and the request
has **no** search, filters or `queryset_filters`, `list()` calls `estimate_row_count()` first:

- estimate `>= count_estimate_threshold` → use it as `total`, with `total_is_estimate=True`;
  no `count(*)` is issued.
- otherwise, or when the adapter cannot estimate (`None`, e.g. SQLite) → exact count, cached
  per `count_cache_ttl` as before.

Any request with search, filters or tenant filters always uses the exact (cached) count, because
the table estimate says nothing about a filtered subset. The list template renders an estimated
total as `~4.2M` and disables the "last page" link (page numbers stay exact up to the data).

The exact count path also drops the `select count(*) from (select ...)` subquery wrapper
(`adapters/sqlmodel.py:154`) when the query has no joins or `DISTINCT`, and counts the table
directly; a subquery wrapper blocks the cheaper plans some databases have for plain counts.

#### A4 — Keyset cursor pagination

New `ListResult` dataclass (replaces the `(items, total)` tuple for paginated paths):

```python
@dataclass
class ListResult:
    items: list[Any]
    total: int | None          # None when pagination_mode == "cursor"
    next_cursor: str | None
    prev_cursor: str | None
    has_next: bool
    has_prev: bool
```

**Cursor format** — opaque to clients, versioned for future changes:
```python
# JSON payload:
{"k": [pk_value, sort_col_value], "d": "next" | "prev", "v": 1}
# Encoded as base64-urlsafe(JSON.dumps(payload).encode()) with no padding.
```
Helpers `encode_cursor()` / `decode_cursor()` live in `core/adapters.py` (or
`core/pagination.py` if the cursor codec grows). Decode raises `InvalidCursorError` on
malformed input → view layer maps to HTTP 400.

**SQL shape** (cursor mode, ASC sort):
```sql
SELECT ... FROM model
WHERE (sort_col, pk) > (cursor.sort_col, cursor.pk)
  AND <queryset_filters>
  AND <user filters>
  AND <search predicates>
ORDER BY sort_col ASC, pk ASC
LIMIT page_size + 1   -- +1 row to detect has_next without an extra query
```

Fetch `page_size + 1` rows; if the extra row is present, `has_next=True` and the last
returned row's `(pk, sort_col)` becomes `next_cursor`. `prev_cursor` is the first returned
row's tuple (with direction `"prev"`).

**Fallback to OFFSET** when:
- `order_by` is `None` and the model has no obvious deterministic primary sort, OR
- the sort column is nullable and contains NULLs in a way that breaks tuple ordering, OR
- `pagination_mode == "offset"` (explicit).

The fallback path emits a `warnings.warn(KeysetFallbackWarning)` so operators learn about it.

### Configuration Changes

New / clarified `AdminOptions` fields:

| Field | Type | Default | BC | Notes |
|---|---|---|---|---|
| `list_select_related` | `list[str] \| None` | `None` | **BREAKING** | `None` now = "load nothing" on list path (was "auto-load all"). Document loudly in CHANGELOG. |
| `detail_select_related` | `list[str] \| None` | `None` | BC | `None` = "auto-detect FK relations needed by `__str__`". Existing implicit behaviour, now explicit. |
| `auto_select_related` | `bool` | `False` | BC | When `True`, view layer derives `list_select_related` from dotted entries in `column_list`. |
| `search_fields` | `list[str] \| None` | `None` (existing) | BC | Was a parity bug in `SQLAlchemyAdapter` (silently ignored). After A2, both adapters honour it. |
| `count_cache_ttl` | `int` (seconds) | `0` | BC | `0` = caching disabled. Must be >= 0. |
| `count_estimate_threshold` | `int \| None` | `None` | BC | `None` = always exact. When set, an unfiltered list total at or above it uses `estimate_row_count()` instead of `count(*)`. Must be > 0. |
| `pagination_mode` | `Literal["offset", "cursor"]` | `"offset"` | BC | `"cursor"` opts into keyset pagination. |

New global on `Admin()` / `HyperAdminSettings`:

| Field | Type | Default | Notes |
|---|---|---|---|
| `count_cache` | `CountCache \| None` | `None` (auto-creates `InMemoryTTLCache` if any model has `count_cache_ttl > 0`) | Inject your own (Redis impl in v0.8) |

No environment-variable surface added in v0.7.0.

### Tests

- **Unit:** `tests/unit/test_selectinload_options.py`, `tests/unit/test_search_fields_parity.py`,
  `tests/unit/test_count_cache.py`, `tests/unit/test_keyset_pagination.py`.
  Each file maps 1:1 to one A-track. Coverage target: 99% on new code (per `testing.md`).
- **E2E:** `tests/e2e/test_keyset_pagination.py` covers pagination_mode="cursor" end-to-end
  (HTMX page-flip via cursor links). Other tracks are pure-backend and stay unit-tested.
- **Performance smoke:** A new fixture seeds 10K rows and asserts query counts for A1
  (≤1 SELECT) and execution-time bounds for A4 (cursor page-100 < 50ms vs offset > 200ms).
  Full 10M-row validation lives in the sibling Locust epic, not in CI.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `load_relations=["does_not_exist"]` | Adapter raises `ValueError("Unknown relation: does_not_exist")` at request time. |
| `auto_select_related=True` with no dotted entries in `column_list` | Derives empty list — no relations loaded. Same as `[]`. |
| `count_cache_ttl > 0` but `count_cache is None` on `Admin()` | `Admin.__init__` constructs a single `InMemoryTTLCache` instance and binds it to all models. |
| Cache key contains non-hashable filter value (e.g., a list) | Cache lookup is skipped; a `logger.debug` line records the miss. Correctness > caching. |
| Cache invalidation across processes | Not supported in v0.7.0 — TTL is the only multi-process correctness boundary. Documented in the migration guide. Redis backend (v0.8) lifts this constraint. |
| `get_queryset()` (RLS) returns different filters per request | Already part of the cache key — different RLS scopes get different cache entries. No cross-tenant leakage. |
| Cursor on non-unique sort column | Tuple `(sort_col, pk)` ensures determinism — pk is the tiebreaker. |
| Cursor on nullable sort column with NULLs | Falls back to OFFSET pagination + warning (NULLs break tuple ordering across DBs differently). |
| Cursor + `get_queryset()` (RLS) | `get_queryset()` is re-applied on every request — cursor decoding does not bypass RLS. |
| Cursor encoding mismatch (`v: 2` from a future version) | `decode_cursor` raises `InvalidCursorError` → 400. Forward-compat is via the `v` field. |
| Many-to-many in `list_select_related` | Supported; SQLAlchemy `selectinload` handles M2M via the secondary table. Documented as opt-in. |
| User changes `pagination_mode` mid-session | Old in-flight cursor URLs return 400 — acceptable. Documented. |
| Search across columns of mixed types when `search_fields=None` | Heuristic only picks string-typed columns — non-string columns are silently skipped. |

## Migration & Backward Compatibility

### A1 — selectinload default change is BREAKING (minor-bump justified)

Switching list-view default from "auto-load all relations" to "load nothing" is observably
different: any template that walks a relation off a list-view item without that relation in
`list_select_related` will issue a lazy-load (or, with async sessions, raise
`MissingGreenlet` / `DetachedInstanceError`). Mitigations:

1. **CHANGELOG note** at the top of v0.7.0:
   *"BREAKING: list views no longer eagerly load all model relations. Add
   `list_select_related=[...]` (or `auto_select_related=True`) to `AdminOptions` for any
   relation rendered in `column_list` or list-view templates."*
2. **Migration guide section** in `docs/migration/v0.7.0.md` walking through the
   one-line fix per registered model.
3. **`auto_select_related=True`** as the recommended drop-in for users who do not want to
   audit each `column_list` manually.

Detail views are **not** affected — `detail_select_related=None` keeps current behaviour.

### A2 — pure bugfix, no migration needed

`SQLAlchemyAdapter` users who relied on the (undocumented) "search every string column"
behaviour will now see search scoped to `search_fields`. If they had `search_fields=None`,
the new heuristic ("string columns minus PK") is functionally identical to the old behaviour
**minus the PK** — operators rarely want to ILIKE-search numeric PKs anyway. Documented in
the upgrade notes.

### A3 — fully BC (default `count_cache_ttl=0` disables caching; `count_estimate_threshold=None` keeps exact totals)

### A4 — fully BC (default `pagination_mode="offset"`)

### Adapter contract evolution

`BaseAdapter.list()` is **deprecated** in v0.7.0 — it keeps working (returns the same
`(items, total)` tuple) and emits a `DeprecationWarning` redirecting to `list_paginated()`.
Removal scheduled for v1.0. Third-party adapters get one cycle to migrate.

`list_paginated()` is added with a default implementation on `BaseAdapter` that calls
`self.list()` and wraps the tuple in `ListResult(total=..., next_cursor=None,
prev_cursor=None, has_next=False, has_prev=False)`. Built-in adapters override it with the
keyset-aware implementation. Third-party adapters keep working unchanged but lose access to
cursor mode until they override.

## Open Questions

- [ ] **Should `column_list` containing relation accessors auto-trigger
      `auto_select_related=True`?** Recommended yes for ergonomics — a user writing
      `column_list=["category.name"]` clearly wants `category` loaded. But silently flipping
      a default contradicts the BREAKING note we are already issuing for A1. **Proposal:**
      keep `auto_select_related=False` as the default in v0.7.0 (explicit-is-better-than-
      implicit), revisit for v0.8 once the explicit migration has settled.
- [ ] **Cache eviction policy for `InMemoryTTLCache`.** TTL alone or LRU+TTL? On a large
      site with many distinct filter combinations, pure TTL can balloon. **Proposal:**
      LRU+TTL with `max_entries=1024` default — bounded memory; tunable via `Admin()`.
- [ ] **Cursor signing.** Cursors are opaque base64 today but **not signed**. A motivated
      attacker could craft a tuple to peek at rows ordered around any value. RLS
      (`get_queryset()`) still applies, so this is not an authz bypass — only a
      enumeration aid. **Proposal:** ship unsigned in v0.7.0; add HMAC signing in v0.7.1
      behind a `pagination_cursor_secret` setting if user feedback raises it.
- [ ] **Should `BaseAdapter.list()` be removed in v1.0 or kept indefinitely?** Removal is
      cleaner but third-party adapters benefit from a stable shim. **Proposal:** decide at
      v0.9 retro based on third-party adapter survey.

- [ ] **Default for `count_estimate_threshold`.** *(added 2026-11-01)* `None` (always exact)
      keeps totals unchanged for every existing deployment, but means nobody benefits until they
      set it. **Proposal:** `None` in v0.7.0 for BC (the displayed total changes from `4,200,001`
      to `~4.2M`); the runtime advisor's slow-count warning recommends the option by name;
      revisit a default of `1_000_000` for v0.8.
- [ ] **Stale estimates.** `reltuples` is only refreshed by `VACUUM`/`ANALYZE`; right after a
      bulk load it can be 0. **Proposal:** treat an estimate `<= 0` as "cannot estimate" and fall
      back to the exact count.

These must be settled before Status → Approved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Single umbrella SDD covering A1-A4 | All four touch `BaseAdapter.list()` / `list_paginated()` — splitting would require duplicating the protocol surface across 4 specs. | 4 separate SDDs (rejected — overlapping surface, hard to keep in sync) |
| List default = "load nothing" (BREAKING) | The status quo is the bug — 5 unconditional SELECTs on every list request is the #1 named bottleneck in the milestone. A pure-additive opt-in fixes nothing for existing users. | Keep "load all" default + add opt-out flag (rejected — does not fix the actual scalability problem; users would not migrate) |
| Detail default kept as auto-detect | `__str__` rendering breaks if FK relations are not loaded; many users rely on this implicitly. | Apply same BREAKING change to detail (rejected — too disruptive, low scalability payoff vs list path) |
| `auto_select_related` opt-in (default False) | Avoids a second silently-flipped default; users who want it can flip one boolean. | Default True (rejected — see Open Question 1) |
| A3 ships in-memory only; Redis deferred to v0.8 | YAGNI — most v0.7.0 deployments are single-process or behind a load balancer with sticky sessions. Redis adds an infra dependency we can't justify yet. | Ship Redis in v0.7.0 (rejected — scope creep; protocol declaration is enough seam) |
| Cache key excludes pagination params | Pagination doesn't change the count — including page would shatter the cache pointlessly. | Include page (rejected — every page-flip would miss) |
| `pagination_mode="offset"` default | Cursor changes pagination URL semantics; flipping default would break every bookmarked admin URL. | Default cursor (rejected — observable URL change) |
| `ListResult` dataclass alongside tuple shape | Lets us evolve the response without re-breaking the tuple contract; `total: None` is the natural cursor-mode signal. | Reuse tuple `(items, total)` with sentinel (rejected — `(items, -1)` is uglier than `total: None`) |
| Versioned cursor (`v: 1` field) | Forward-compat — we will tighten the shape (signing, additional sort cols) without breaking deployed cursors. | Bare base64 of `(pk, sort_col)` (rejected — no upgrade path) |
| Estimate only for unfiltered lists, opt-in threshold (2026-11-01) | Dogfood scale tests: the unfiltered default page is the common slow count; a table estimate says nothing about a filtered subset, and a few records of error do not matter at millions of rows. Matches the maintainer's Django practice (`reltuples` after a few million rows, short-lived exact count below). | Estimate for filtered counts (wrong numbers); always estimate (changes totals for everyone); cache only (first hit still slow) |
| `count()` and `estimate_row_count()` coexist | Two different trade-offs (exact-with-filters vs approximate-without). One method can't be both. | Single overloaded method (rejected — confusing call site) |
| `core/cache.py` module shared with epic #213 | Both epics need a generic TTL cache; one module avoids duplication. The module is owned by #213's SDD; this SDD declares only the consumer-facing `CountCache` Protocol shape. | Two separate cache modules (rejected — duplicate eviction logic) |
| Deprecate `list()` in v0.7.0, remove in v1.0 | One-cycle deprecation respects third-party adapter authors and is the project's stated semver discipline. | Hard-remove in v0.7.0 (rejected — too aggressive for a `0.x.0` minor) |
| Pagination template logic in `components/pagination.html` | Existing partial included from `components/table.html:44`; cleanest place for cursor/page branching. | New `cursor_pagination.html` partial (rejected — duplicates surrounding markup) |
