# SDD: Runtime Advisor (per-view performance budgets with actionable warnings)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #779 |
| Milestone | v0.7.0 — High-Volume & High-Load Scalability |
| Created | 2026-10-30 |
| Last updated | 2026-10-30 |

---

## Problem

Scale tests on 1M and 10M-row tables (SQLite and Postgres) showed that the slow cases are few, predictable and fixable by configuration:

| Observation (10M-row SQLite) | Cause |
|---|---|
| A search took ~11 s on a 4.2M-row table | `ILIKE '%term%'` over every inferred string column: a full scan, no index can serve it |
| A list of a 3.4M-row table took 2.3 s | `count(*)` had no small index to count through |
| A list of an 840k-row table took ~1.2 s | most likely the default sort (first model field) has no index, so every page sorts the whole table (an unindexed `ORDER BY ... LIMIT 10` on that table measured ~2 s in isolation; the exact column the list used was not confirmed) |
| A page halfway through a 4.2M-row table took 4.6 s | `OFFSET` walks past every skipped row |
| A JSON column in the list made one page 1.95 MB | a whole document rendered in a cell (fixed separately) |

Nothing tells the developer. The admin is simply slow, and the cause and the fix are found by profiling. The remedies are partly in place (`search_fields`) and partly planned (#211: count cache and cursor pagination; #213: `estimate_row_count()`), but a developer only turns them on if they know they need them.

Typical healthy numbers from the same runs, at the default page size of 10: list pages were 15–120 ms and 38–80 KB; detail pages 3–10 ms. A tight budget separates healthy from unhealthy cleanly.

## Goals

- Give each kind of view a **budget** (time, and for lists also response size). When a view exceeds its budget repeatedly, log **one actionable warning per (model, case)** naming the model, the measurement and the concrete fix.
- On a breach, **diagnose** the cause from data the request already produced (count time, items time, offset, sort, search, response size) and recommend the matching fix.
- Static checks at mount that need no traffic: inspect models and mappers, no database access.
- Negligible cost always (clock reads, a body-length counter); no extra queries.
- Off switch (`HYPERADMIN_ADVISOR=off`) and per-model silencing (`advisor_ignore`).
- Recommendations name only options that exist; planned options are marked "when available".

## Non-Goals

- Fixing anything automatically, or changing behaviour. The advisor only reports.
- `EXPLAIN` or any additional database query.
- A UI health panel or banner (possible later; the `Advice` records make it easy).
- Metrics export or tracing (the logfire plugin covers observability).
- Client-side or network timing: budgets cover server handling time only (time waiting on the request body is subtracted).

## BDD Scenarios

The scenarios are the ones in #779; each maps to one unit test.

```
Scenario: a repeatedly slow search on a large table warns once with a fix
  Given a list view with a 200 ms budget and a model with 1M rows
  When  two search requests each take longer than 200 ms
  Then  one warning with code HA-R004 is logged naming the model, the duration and the matching row count
  And   a third slow request does not log it again

Scenario: a single slow request does not warn
  Given the same list view
  When  only one request exceeds its budget (a cold first hit)
  Then  no warning is logged

Scenario: an oversized list page recommends fewer rows or columns
  Given a list view with a 100 KB budget
  When  two list responses are larger than 100 KB
  Then  a warning with code HA-R020 is logged recommending a smaller page_size or fewer list_display columns

Scenario: a slow detail page is flagged
  Given a detail view with a 50 ms budget
  When  two detail requests take longer than 50 ms
  Then  a warning with code HA-R030 is logged

Scenario: a deep offset is named as the cause
  Given a list request over budget whose offset is at least 100000
  When  the breach is diagnosed
  Then  the warning is HA-R003 and recommends filters (cursor pagination when available)

Scenario: a slow file upload is not held to the write budget
  Given a multipart request that saves a file and takes longer than 300 ms to handle
  When  it completes repeatedly
  Then  no warning is logged

Scenario: time spent receiving the request body is not counted
  Given a write whose handler takes 50 ms but whose client sends the body over 2 s
  When  it completes
  Then  the measured time is about 50 ms and no warning is logged

Scenario: login hashing is not flagged
  Given a password login that takes 400 ms because of the password hash
  When  it completes repeatedly
  Then  no warning is logged

Scenario: an unindexed default sort is flagged at mount
  Given a registered model whose default sort column has no index and is not the primary key
  When  the admin is mounted
  Then  a warning with code HA-S003 is logged, without any database query

Scenario: a wide inferred search is flagged at mount
  Given a model with four or more inferred search columns and no explicit search_fields
  When  the admin is mounted
  Then  a warning with code HA-S002 recommends setting search_fields

Scenario: the advisor can be turned off
  Given HYPERADMIN_ADVISOR=off
  When  views exceed their budgets
  Then  no advisor warning is logged

Scenario: a code can be silenced per model
  Given AdminOptions(advisor_ignore={"HA-R004"}) on a model
  When  slow searches occur on that model
  Then  no HA-R004 warning is logged for it
```

## Design

### Architecture

New feature package `src/hyperadmin/advisor/`:

```
advisor/records.py     Advice, Observation (frozen dataclasses)
advisor/checks.py      static checks and the breach diagnosis (pure functions)
advisor/middleware.py  pure-ASGI middleware: times the request, counts body bytes, reports
advisor/__init__.py    Advisor (breach counter, once-only dedupe, emit)

core/app.py            one mount hook: add the middleware, run static checks
adapters/sqlalchemy.py, adapters/sqlmodel.py
                       record count_ms / items_ms / offset / sort / searched for the request
```

- **Request timing and size live in the middleware** because neither is visible inside an adapter: it wraps the app, notes the start time, sums `http.response.body` bytes, and on completion hands the advisor a `RequestFacts(route_kind, model, ms, bytes)`.
- **Adapter facts.** `list()` already runs a count query and an items query. It wraps each in `time.perf_counter()` and stores `QueryFacts(count_ms, items_ms, total, offset, sort_field, searched)` in a request-scoped `ContextVar`. The middleware merges it when the response completes. No signature change to `BaseAdapter.list()`.
- **Route kind.** The middleware classifies a request from the matched route name, the method and the `Content-Type` (`list`, `detail`, `form`, `write`, `upload`, `bulk`, `choices`, `auth`, `other`). Route names are already consistent in the dynamic router (`{model}-detail`, `{model}-update-form`, ...); a `multipart/form-data` write is an `upload`, and the auth package's routes are `auth`.
- `advisor/` imports `core/` for introspection and `AdminOptions`; `core/app.py` imports `advisor/` at the one mount hook. No import goes the other way, and `adapters/` only writes to the `ContextVar` defined in `advisor/records.py`.
- Emission goes to the logger `hyperadmin.advisor` at `WARNING`, so it appears in the console and in any log pipeline. Existing precedent: the composite-key warning in `routing.py`.

### Budgets

A request breaches when it exceeds the time budget **or** the size budget of its route kind. Defaults:

| Route kind | Time | Response size | Notes |
|---|---|---|---|
| `list` (page, sort, search and filter requests all land here) | 200 ms | 100 KB | healthy default page: 15–120 ms, 38–80 KB |
| `detail` | 50 ms | 250 KB* | healthy: 3–10 ms |
| `form` (create / edit GET)* | 100 ms | 250 KB* | |
| `write` (non-multipart POST / PUT / PATCH / DELETE)* | 300 ms | n/a | |
| `upload` (multipart request: file or image fields)* | none | n/a | thumbnailing and storage writes are legitimately slow; opt in per budget |
| `bulk` (bulk actions on selected rows)* | 1000 ms | n/a | scales with the selection |
| `choices` (relation autocomplete, typed search)* | 100 ms | 20 KB* | fires on keystrokes |
| `auth` (login, logout, password and MFA routes)* | none | n/a | password hashing is slow by design |
| `other` (dashboard, index, anything else)* | 500 ms | 250 KB* | |

\* proposed; the list and detail figures are the ones requested, the rest follow the same logic and are open for review. A budget of `none` is never checked; setting a number in `advisor_budgets` opts that kind in.

**Server time only.** The middleware wraps `receive()` and subtracts the time the app spends waiting for the request body, so a slow client uploading over a slow link never counts against the budget. What remains is time spent handling the request.

A breach counts toward a warning only when it is the **second** breach of the same `(model, route kind)` since process start (see Edge Cases). The first request to every route is excluded entirely, as warm-up.

### Diagnosis (what the warning says)

A breaching `list` request is classified in this order, using the facts already collected:

| Code | Condition | Recommendation |
|---|---|---|
| HA-R003 | `offset ≥ 100_000` | the database reads past every skipped row; add filters (cursor pagination when available, #211) |
| HA-R004 | the request was a search and `items_ms` is over half the request time | set `search_fields` to the one or two columns people search; on Postgres add a `pg_trgm` GIN index; on SQLite no index can serve a substring search |
| HA-R001 | `count_ms ≥ 100` and over half the request time | narrow the default filters; when available, use the count cache and the approximate count (#211, #213) |
| HA-R002 | `items_ms ≥ 100`, not a search, and a sort field in play | index the sort column, or sort by an indexed column |
| HA-R020 | the size budget was breached (time was fine) | lower `page_size`, drop wide columns from `list_display`; JSON and long text are already shortened |
| HA-R010 | none of the above (the time is neither count nor items) | likely relationship loading or rendering; review the model's relationships (selectinload options when available, #211) |

`detail` and `form` breaches give HA-R030 and HA-R031: *the page is over budget; check relationship loading and any expensive property on the model.* `write`, `bulk`, `choices` and `other` breaches give a short generic warning (HA-R040, HA-R041, HA-R050, HA-R060) naming the budget and the measurement. `upload` and `auth` have no budget by default, so they never warn unless a budget is set.

The "rows" figure in a message is the **matching** row count (the filtered total the page already computed), and the message says "matching" when a search or filter was active.

### Static checks (at mount, no database access)

| Code | Trigger | Recommendation |
|---|---|---|
| HA-S001 | a JSON column is in an explicit `list_display` | remove it from `list_display`; it is shown in full on the detail page (list cells are truncated to one line) |
| HA-S002 | ≥ 4 inferred search columns and no explicit `search_fields` | set `search_fields` to the one or two columns people really search; every inferred column is scanned with `ILIKE '%term%'` |
| HA-S003 | the default sort column is not the primary key and has no index | add an index to that column, or reorder the model fields so an indexed column is first |
| HA-S004 | a column's annotation and its SQLAlchemy type disagree (for example `str` over `Boolean`) | fix the annotation; the field is otherwise searched and rendered as the wrong type |

Message format (one record, three lines):

```
[HA-R004] Recipe: search took 10.8 s (budget 200 ms) on ~4.2M matching rows.
  Fix: set search_fields=["name"] on this model, or add a pg_trgm GIN index (Postgres).
  Silence: advisor_ignore={"HA-R004"} or HYPERADMIN_ADVISOR=off
```

### Data Model Changes

No data model changes.

### API / Protocol Changes

```python
@dataclass(frozen=True, slots=True)
class Advice:
    code: str          # "HA-R004"
    model: str
    problem: str       # what was measured, with the budget
    fix: str           # what to do

@dataclass(frozen=True, slots=True)
class QueryFacts:      # written by the adapter into a request-scoped ContextVar
    count_ms: float
    items_ms: float
    total: int
    offset: int
    sort_field: str | None
    searched: bool

class Advisor:
    def check_models(self, models, options_for) -> list[Advice]: ...        # static, at mount
    def observe(self, route_kind, model, ms, nbytes, facts) -> Advice | None  # runtime
```

`BaseAdapter.list()` signature is unchanged. Nothing is added to `__init__.py` exports in this iteration (`Advice` stays internal until a UI panel needs it).

### Configuration Changes

`HyperAdminSettings` (env prefix `HYPERADMIN_`):

| Setting | Default | Meaning |
|---|---|---|
| `advisor` | `"warn"` | `"warn"` or `"off"` |
| `advisor_budgets` | the table above | per route kind `{"list": {"ms": 200, "kb": 100}, ...}`; override single keys |
| `advisor_breaches` | `2` | breaches of one `(model, route kind)` before the first warning |
| `advisor_deep_offset` | `100_000` | HA-R003 threshold |

`AdminOptions.advisor_ignore: set[str] = set()` silences codes for one model.

## Edge Cases & Error Handling

- **Never breaks a request.** The middleware, `observe` and the static checks catch every exception and log it at `DEBUG`. A failure to read a body chunk never alters the response.
- **Warm-up.** In the five scale-test runs up to 1M rows, the first model requested (a table of at most a few thousand rows) was among the five slowest requests every time, and the slowest in four of them (230–370 ms): lazy schema build, template compilation, cold database cache. The first request per `(model, route kind)` is therefore ignored, and a warning needs `advisor_breaches` (default 2) breaches. A one-off slow request never warns.
- **Dedupe.** One warning per `(model, code)` per process, in a set guarded by a lock. A restart logs it again, by design.
- **Tight budgets, noisy hardware.** A busy or slow CI machine can breach 200 ms legitimately. The advisor is off in the project's own test suite (`advisor="off"`), and the budgets are settings so slower environments can relax them.
- **Streaming responses.** Size is summed from `http.response.body` chunks as they pass; nothing is buffered.
- **Multiple workers.** Each process warns on its own; there is no cross-process coordination.
- **Static checks on exotic models.** A model whose mapper cannot be inspected is skipped silently (DEBUG log).

## Migration & Backward Compatibility

Backward compatible; no migration. It adds one ASGI middleware, log lines and settings with defaults. Default is `"warn"` (decided with the maintainer: the audience is people who do not know they need it). A deployment that cannot tolerate the extra middleware can set `HYPERADMIN_ADVISOR=off`, in which case the middleware is not installed at all.

## Open Questions

1. **Budgets beyond list and detail.** The `form`, `write`, `choices` and `other` figures are proposals. Which should change?
2. **Size budgets beyond the list.** Is a 250 KB catch-all for the other HTML views reasonable, or should only lists have a size budget?
3. **Breach count.** Two breaches before warning removes warm-up noise but delays the first warning on a quiet admin. Is 2 right, or 3?
4. **Query count.** Counting SQL statements per request (a SQLAlchemy `before_cursor_execute` hook) would let `detail`/`form` breaches name an N+1 pattern ("47 queries for one page"). Worth adding as HA-R032 in this iteration, or later?
5. **HA-S003 wording** depends on whether a `default_sort` option is added in #211. Until then the text says "index the column or reorder the fields".
6. **Static check for `list_filter` columns without an index** (a likely fifth static code)?
7. **UI surface.** Should a later iteration show `Advice` records in an admin "health" panel?

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Per-view budgets (time and size) as the trigger, diagnosis second | Matches what a user feels ("this page is slow or heavy"); needs no table-size guess; the cause is then read from data the request already produced | Row-count gates and per-query thresholds (miss slow pages caused by rendering and relationships; need a count to decide anything) |
| A request-level middleware | Total time and response size are not visible inside an adapter | Wrap each view handler (touches every view, and misses non-dynamic views) |
| Subtract time spent waiting on the request body; uploads and auth routes get no time budget | A slow client link is not a server problem; image processing and password hashing are slow on purpose, and a flat write budget would flag healthy requests | A single higher write budget (still wrong for a 50 MB upload, and hides real slow writes); excluding all writes (misses slow validation and hooks) |
| Warn on the second breach, ignore the first request | Measured warm-up noise on every run | Warn immediately (false positives on every restart); a warm-up timer (state and timing sensitivity) |
| Report only, never change behaviour | Safe to turn on everywhere; keeps remedies explicit and reviewable | Auto-narrow the search or auto-switch to cursor paging (surprising, and changes results) |
| Reuse timings the adapter already measures | No extra queries, no `EXPLAIN` cost or permission issues | `EXPLAIN` the query (accurate, but an extra round trip with per-dialect output) |
| Static checks at mount, runtime checks lazily | Mount must not touch the database; some problems only show with real data volume | Probe row counts at mount (a count per model at startup is the problem we warn about) |
| Standard logger `hyperadmin.advisor` | Works with existing log config and the logfire plugin; precedent in `routing.py` | Print to stdout; a custom hook system |
| Dedupe per (model, code) per process | Avoids log spam on busy admins | Rate limit by time (more state, harder to test) |
| Budgets as settings | The right numbers differ by hardware and database | Hard-coded constants |
