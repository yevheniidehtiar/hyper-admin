# SDD: Runtime Advisor (actionable performance warnings)

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

## Goals

- Log **one actionable warning per (model, case)** the first time a problem is detected, naming the model, the measurement and the concrete fix.
- Two detectors: **static** checks at mount (inspect models and mappers, no database access) and **runtime** checks (read timings the adapter already measures, no extra queries).
- Zero cost when healthy; negligible cost always (two clock reads per list request).
- Off switch (`HYPERADMIN_ADVISOR=off`) and per-model silencing (`advisor_ignore`).
- Recommendations name only options that exist; planned options are marked as such.

## Non-Goals

- Fixing anything automatically, or changing behaviour. The advisor only reports.
- `EXPLAIN` or any additional database query.
- A UI health panel or banner (possible later; the `Advice` records make it easy).
- Metrics export or tracing (the logfire plugin covers observability).
- Advising on non-list views (detail, create, edit) in this iteration.

## BDD Scenarios

The scenarios are the ones in #779; each maps to one unit test.

```
Scenario: a slow search on a large table produces one warning with a fix
  Given a model with 1M+ rows and several inferred string search columns
  When  a search request takes longer than the slow-query threshold
  Then  one warning with code HA-R004 is logged naming the model, the duration and the row count
  And   repeating the request does not log it again

Scenario: an unindexed default sort is flagged at mount
  Given a registered model whose default sort column has no index and is not the primary key
  When  the admin is mounted
  Then  a warning with code HA-S003 is logged, without any database query

Scenario: a wide inferred search is flagged at mount
  Given a model with four or more inferred search columns and no explicit search_fields
  When  the admin is mounted
  Then  a warning with code HA-S002 recommends setting search_fields

Scenario: a slow count recommends the count options
  Given a list request whose count query takes longer than the count threshold
  When  the list page is served
  Then  a warning with code HA-R001 is logged

Scenario: a deep offset is flagged
  Given a list request whose offset exceeds the deep-offset threshold
  When  the page is served
  Then  a warning with code HA-R003 is logged

Scenario: the advisor can be turned off
  Given HYPERADMIN_ADVISOR=off
  When  slow or misconfigured models are used
  Then  no advisor warning is logged

Scenario: a code can be silenced per model
  Given AdminOptions(advisor_ignore={"HA-R004"}) on a model
  When  a slow search occurs on that model
  Then  no HA-R004 warning is logged for it
```

## Design

### Architecture

```
core/advisor.py          Advice, Observation, check registry, once-per-(model, code) dedupe, emit
   ▲            ▲
   │ static     │ runtime
core/app.py     adapters/sqlalchemy.py, adapters/sqlmodel.py
(mount hook)    (time the count and items queries, report an Observation)
```

- `core/advisor.py` is pure logic: no I/O except the logger, no import of `adapters/` or `views/` (dependency flows into `core`, never out).
- Static checks run once from `Admin.mount()` over the registered models, using `core/introspection` and SQLAlchemy mapper metadata (`Column.index`, `Table.indexes`, `primary_key`).
- Runtime checks: the adapters already run a count query and an items query in `list()`. They wrap each in `time.perf_counter()` and pass an `Observation(model, total, count_ms, items_ms, offset, page_size, sort_field, searched)` to `advisor.observe(...)`. The advisor decides; the adapter never raises because of it (`observe` swallows its own errors).
- Emission goes to the logger `hyperadmin.advisor` at `WARNING`, so it appears in the console and in any log pipeline without new plumbing. Existing precedent: the composite-key warning in `routing.py`.

### Checks

Static (at mount, no database access):

| Code | Trigger | Recommendation |
|---|---|---|
| HA-S001 | a JSON column is in an explicit `list_display` | remove it from `list_display`; it is shown in full on the detail page (list cells are truncated to one line) |
| HA-S002 | ≥ 4 inferred search columns and no explicit `search_fields` | set `search_fields` to the one or two columns people really search; every inferred column is scanned with `ILIKE '%term%'` |
| HA-S003 | the default sort column is not the primary key and has no index | add an index to that column, or reorder the model fields so an indexed column is first |
| HA-S004 | a column's annotation and its SQLAlchemy type disagree (for example `str` over `Boolean`) | fix the annotation; the field is otherwise searched and rendered as the wrong type |

Runtime (from the adapter timings; `total` is the count the list already computed):

| Code | Trigger (defaults) | Recommendation |
|---|---|---|
| HA-R001 | `count_ms ≥ 500` | narrow the default filters; when available, enable the count cache and the approximate count (#211, #213) |
| HA-R002 | `items_ms ≥ 1000`, no search, and `total ≥ 100_000` | the sort column probably has no index: index it, or sort by an indexed column |
| HA-R003 | `offset ≥ 100_000` | the database reads past every skipped row, so cost grows with the offset; when available, use cursor pagination (#211); until then, add filters |
| HA-R004 | a search request with `items_ms ≥ 1000` and `total ≥ 100_000` | set `search_fields` to fewer columns; on Postgres add a `pg_trgm` GIN index on the column; on SQLite there is no substring index, so narrow the search |

Message format (one record, two lines):

```
[HA-R004] Recipe: search took 10.8 s on ~4.2M rows.
  Fix: set search_fields=["name"] on this model, or add a pg_trgm GIN index (Postgres).
  Silence: advisor_ignore={"HA-R004"} or HYPERADMIN_ADVISOR=off
```

### Data Model Changes

No data model changes.

### API / Protocol Changes

New module `hyperadmin.core.advisor`:

```python
@dataclass(frozen=True, slots=True)
class Advice:
    code: str          # "HA-R004"
    model: str
    problem: str       # what was measured
    fix: str           # what to do

@dataclass(frozen=True, slots=True)
class Observation:
    model: str
    total: int
    count_ms: float
    items_ms: float
    offset: int
    page_size: int
    searched: bool
    sort_field: str | None

class Advisor:
    def check_models(self, models, options_for) -> list[Advice]: ...   # static, at mount
    def observe(self, obs: Observation) -> Advice | None: ...          # runtime, once per (model, code)
```

`BaseAdapter.list()` gains no signature change; the two adapters call `advisor.observe(...)` after their existing queries. The advisor instance is reachable from the adapter via the `Admin` instance already passed to it. Nothing is added to `__init__.py` exports in this iteration (`Advice` stays internal until a UI panel needs it).

### Configuration Changes

`HyperAdminSettings` (env prefix `HYPERADMIN_`):

| Setting | Default | Meaning |
|---|---|---|
| `advisor` | `"warn"` | `"warn"` or `"off"` |
| `advisor_count_ms` | `500` | HA-R001 threshold |
| `advisor_query_ms` | `1000` | HA-R002 and HA-R004 threshold |
| `advisor_min_rows` | `100_000` | minimum table size for R002 and R004 |
| `advisor_deep_offset` | `100_000` | HA-R003 threshold |

`AdminOptions.advisor_ignore: set[str] = set()` silences codes for one model.

## Edge Cases & Error Handling

- **Never breaks a request.** `observe` and the static checks catch every exception and log it at `DEBUG`.
- **Dedupe.** One warning per `(model, code)` per process, held in a set guarded by a lock. A restart logs it again, by design.
- **Cold cache.** The first request after a restart is often slow only because of a cold database cache. The runtime checks therefore need the measurement to exceed the threshold **and** the table to be large (`advisor_min_rows`), so a slow first hit on a small table never warns.
- **Estimate accuracy.** `total` is the count the page already computed, so it is exact for the filtered set, and a warning's "rows" figure refers to the filtered rows, not the table. The message says "matching rows" when a filter or search was active.
- **Tests and CI.** The test suite builds its own `Advisor` or sets `advisor="off"`, so existing tests are not noisy.
- **Multiple workers.** Each process warns once; there is no cross-process coordination.
- **Static checks on exotic models.** A model whose mapper cannot be inspected is skipped silently (DEBUG log).

## Migration & Backward Compatibility

Backward compatible; no migration. It adds log lines (a behaviour change only for log consumers) and settings with defaults. Default is `"warn"` because the value is in telling people who have not thought about it (see Open Questions).

## Open Questions

1. **Default on or off?** Recommendation: **on** (`"warn"`), since the audience is people who do not know they need it, and it logs at most a handful of lines per model per process. Alternative: on only when `debug=True`.
2. **Thresholds.** 500 ms count, 1000 ms query, 100k rows, 100k offset come from the scale tests on one laptop. Are these the right defaults, or should the thresholds scale with `page_size`?
3. **HA-S003 recommendation wording** depends on whether a default-sort option is added to `AdminOptions` (today the default is "first model field"). If a `default_sort` option is added in #211, the fix text should name it. Until then the text says "index the column or reorder the fields".
4. **Scope of static checks.** Include a check for `list_filter` columns without an index (a likely fifth static code)?
5. **UI surface.** Should a later iteration show `Advice` records in an admin "health" panel? Out of scope here; the data shape allows it.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Report only, never change behaviour | Safe to turn on everywhere; keeps remedies explicit and reviewable | Auto-narrow the search or auto-switch to cursor paging (surprising, and changes results) |
| Reuse timings the adapter already measures | No extra queries, no `EXPLAIN` cost or permission issues | `EXPLAIN` the query (accurate, but extra round trip, per-dialect output) |
| Static checks at mount, runtime checks lazily | Mount must not touch the database; some problems only show with real data volume | Probe row counts at mount (a count per model at startup is the problem we are warning about) |
| Standard logger `hyperadmin.advisor` | Works with existing log config and the logfire plugin; precedent in `routing.py` | Print to stdout; a custom hook system |
| Dedupe per (model, code) per process | Avoids log spam on busy admins | Rate limit by time (more state, harder to test) |
| Thresholds as settings | The right numbers differ by hardware and database | Hard-coded constants |
