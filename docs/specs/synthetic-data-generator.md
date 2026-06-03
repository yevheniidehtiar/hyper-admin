# SDD: Synthetic Data Generator (Faker + Bulk Inserts for 10M+ Records)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | #246 |
| Milestone | v0.7.1 — Load Testing & Synthetic Data |
| Created | 2026-05-05 |
| Last updated | 2026-06-03 |

---

## Problem

The current `examples/erp/seed.py` script issues per-row inserts via the SQLModel session. In
practice this clocks in at **~10–50 inserts/sec** on PostgreSQL — so seeding even a single
million rows takes hours, and 10M is a non-starter. That is fine for a "five demo invoices"
dev fixture, but it is the wrong tool for the workloads now coming online in v0.7.0:

- **#211 (server-side pagination at 1M+ rows)** needs realistic, non-trivially-distributed
  datasets to expose query-plan regressions and pagination edge cases.
- **#213 (admin list-view scalability targets)** asks for `<200 ms` p95 on tables of 10M rows.
  Both issues need a way to *produce* such tables in CI and on developer machines without
  borrowing production data.

There is no second concern bigger than throughput: foreign-key referential integrity has to
hold across millions of rows, and the distribution of FK references must be **skewed** (a few
"hot" parents own most of the children, mirroring real systems) so the benchmarks remain
representative. A uniform-random FK pool would understate index seek cost and cache pressure.

Without a dedicated bulk seeder, every scalability story in v0.7.0 either invents an ad-hoc
script or runs against unrealistic data. Both paths waste agent time and produce benchmark
numbers we cannot trust.

## Goals

- **Throughput:** sustained **50K–100K inserts/sec on PostgreSQL** as the aspirational target.
  The SQLAlchemy Core baseline (~30K/s on a developer laptop) is the **acceptable v0.7.1
  ship floor**; faster fast-paths are deferred (see Decision Log).
- **FK referential integrity:** every child row references a parent row that exists, even when
  parents and children are inserted in separate batches.
- **Realistic skew:** FK references follow a **Pareto distribution** (`a=1.16`, ≈80/20 rule)
  so a small subset of accounts owns most invoices, mirroring real ERP shapes.
- **Resumability:** Ctrl-C or process kill can be resumed from the last completed batch
  without producing duplicate rows or leaving orphan FKs.
- **Observability:** Rich progress UI with per-table progress bars, ETA, throughput
  (rows/sec), and total elapsed time.
- **CLI ergonomics:** a single `hyperadmin seed --count N` command drives the full plan; no
  per-table invocation.
- **Determinism:** default RNG seed = `42` so CI runs are byte-reproducible.
- **No new runtime dependencies:** numpy is a *soft* dependency with a stdlib fallback;
  Faker is already a dev dep.

## Non-Goals

- **Auto-discovery of arbitrary user models** from SQLModel metadata. v0.7.1 ships a
  hard-coded ERP plan; generic discovery is deferred to **v0.8**.
- **MySQL / MariaDB tuning.** PostgreSQL is the v0.7.0/v0.7.1 reference target. SQLite is
  supported via param-limit shrinking but is not benchmarked.
- **UI-triggered seeds.** The seeder is a CLI/operator tool. There is no `/admin/seed` button.
- **Replacing the superuser bootstrap.** `examples/erp/seed.py` keeps its existing role of
  creating the demo superuser; the bulk seeder is *additive*.
- **COPY / `psycopg.copy_expert` fast path** in v0.7.1. Considered and deferred (see
  Decision Log).
- **Spill-to-disk FK pools** for >100M-row parents. Pools are in-memory `dict[str, list[int]]`
  in v0.7.1; a DB-backed pool is future work if benchmarks demand it.
- **Multi-process / multi-worker parallel seeding.** Single-process producer/consumer is
  enough to hit the throughput floor; parallelism is deferred.

## BDD Scenarios

```
Scenario: bulk seed produces N rows across the ERP plan
  Given a fresh PostgreSQL database with the ERP schema migrated
  When  `hyperadmin seed --count 10000 --batch-size 5000` is run
  Then  the process exits 0
  And   each ERP table contains its planned share of the 10000 rows
  And   the Rich progress UI reports a final throughput >= 10000 rows / elapsed_seconds

Scenario: foreign-key integrity is preserved across batches
  Given the ERP plan inserts Accounts before Invoices
  When  the seeder commits an Invoices batch
  Then  every invoice.account_id row exists in the Accounts table
  And   no batch is committed before its parents' FK pool is populated

Scenario: Ctrl-C mid-run resumes from the last completed batch
  Given the seeder is mid-run with 6 of 20 batches committed
  When  the operator sends SIGINT
  And   re-runs `hyperadmin seed --count N --resume`
  Then  the run continues from batch 7
  And   the final row count equals N (no duplicates, no gaps)
  And   `.hyperadmin-seed.json` is removed on clean completion

Scenario: FK reference distribution follows the configured Pareto skew
  Given a seed with 1000 Accounts and 100000 Invoices
  When  invoice.account_id values are tallied
  Then  the top 20% of accounts own ~80% of invoices (within +/- 5%)
  And   no account_id is referenced more often than mathematically possible

Scenario: schema-drift on resume aborts cleanly
  Given a checkpoint file written for plan_hash A
  And   the loaded plan now hashes to B
  When  `hyperadmin seed --resume` is invoked
  Then  the seeder exits non-zero with a clear "plan hash mismatch" message
  And   no rows are written

Scenario: unique-constraint exhaustion does not deadlock the run
  Given a column with a UNIQUE constraint and a small Faker value space
  When  a generated batch would collide with an existing row
  Then  the batch is regenerated with a per-batch sequence prefix
  And   the run continues without manual intervention
```

## Design

### Architecture

A new top-level module `src/hyperadmin/loadtest/` owns the seeder. It is independent of the
admin core (no `Admin()` coupling) and consumed only by the new Typer subcommand and by
`examples/erp/seed.py`'s superuser bootstrap.

```
src/hyperadmin/
├── loadtest/                          (NEW MODULE)
│   ├── __init__.py                    # Public API: BulkSeeder, SeedPlan, FKPool
│   ├── plan.py                        # SeedPlan, TablePlan dataclasses + plan_hash()
│   ├── pool.py                        # FKPool with Pareto sampling
│   ├── batch.py                       # BulkSeeder: generator → batch → insert loop
│   ├── progress.py                    # Rich progress wrapper (lazy import)
│   ├── checkpoint.py                  # JSON state file: write/read/validate
│   └── generators/
│       ├── __init__.py
│       ├── erp.py                     # Hard-coded ERP plan (Accounts → ... → Lines)
│       └── auth.py                    # Auth tables plan (Users, Groups)
│
├── management/
│   └── commands/
│       └── seed.py                    # Typer subcommand `hyperadmin seed`
│
tests/
├── unit/loadtest/
│   ├── test_pool.py                   # #250 — Pareto distribution, FK pool ops
│   ├── test_batch.py                  # #248 — batch generator unit tests
│   ├── test_checkpoint.py             # #252 — resumable seeding
│   └── test_plan.py                   # plan_hash determinism
└── e2e/
    └── test_seed_integration.py       # #255 — seed 1K rows, verify FK integrity

examples/erp/seed.py                   # #256 — keeps superuser bootstrap; new async wrapper
                                       #         calls BulkSeeder.run() in a thread
```

**Sub-issue mapping:**

| Sub-issue | Module / file |
|---|---|
| #248 test: unit tests for bulk insert batch generator | `tests/unit/loadtest/test_batch.py` |
| #249 feat(loadtest): batch data generator with Faker + SQLAlchemy Core | `loadtest/batch.py` |
| #250 test: unit tests for FK relationship pool and Pareto distribution | `tests/unit/loadtest/test_pool.py` |
| #251 feat(loadtest): FK ID pool manager with Pareto distribution | `loadtest/pool.py` |
| #252 test: unit tests for progress reporting and resumable seeding | `tests/unit/loadtest/test_checkpoint.py` |
| #253 feat(loadtest): Rich progress bar and resumable seeding | `loadtest/progress.py`, `loadtest/checkpoint.py` |
| #254 feat(loadtest): Typer CLI `hyperadmin seed` subcommand | `management/commands/seed.py` |
| #255 test: integration test — seed 1K records, verify FK integrity | `tests/e2e/test_seed_integration.py` |
| #256 refactor(examples): migrate seed.py to use bulk seeder | `examples/erp/seed.py` |

**Flow diagram:**

```
        ┌─────────────────────────┐
        │  hyperadmin seed CLI    │
        │  (Typer, management/)   │
        └────────────┬────────────┘
                     │ flags + plan_hash
                     ▼
        ┌─────────────────────────┐      ┌─────────────────────┐
        │   BulkSeeder.run()      │◄────►│  CheckpointStore    │
        │   (loadtest/batch.py)   │      │  .hyperadmin-       │
        └────┬────────────┬───────┘      │   seed.json         │
             │            │              └─────────────────────┘
             │            │                       ▲
             │            │ insert().values(batch)│ fsync per 100 batches
             │            ▼                       │
             │   ┌─────────────────┐              │
             │   │ SQLA Core engine│              │
             │   │  (PG / SQLite)  │              │
             │   └─────────────────┘              │
             │                                    │
             │ sample()                           │
             ▼                                    │
        ┌─────────────┐    feeds parent IDs       │
        │   FKPool    │◄──────────────────────────┘
        │ (in-memory) │
        └──────┬──────┘
               │ Pareto(a=1.16)
               ▼
        ┌─────────────────────┐
        │ Faker + sequence    │
        │  prefix → row dict  │
        └─────────────────────┘
                  │
                  ▼
           Rich Progress UI
        (loadtest/progress.py)
```

The seeding order is fixed by `generators/erp.py`:

```
Accounts → Contacts → Invoices → InvoiceItems → Bills → BillItems
                                            ↘ JournalEntries → JournalLines
Auth tables (Users, Groups) seed independently of the ERP chain.
```

Parents must complete before children begin so the FK pool is fully populated when the child
table starts. This is encoded in `SeedPlan.tables` ordering and validated at plan-build time.

### Data Model Changes

**No DB schema changes.** The seeder only consumes the existing ERP and auth schemas.

The only new on-disk artifact is the **checkpoint state file**:

```json
{
  "plan_hash": "sha256:<64 hex chars>",
  "rng_seed": 42,
  "started_at": "2026-05-05T10:15:00Z",
  "tables": {
    "accounts":     {"target": 1000,   "completed": 1000,  "last_pk": 1000},
    "invoices":     {"target": 100000, "completed": 35000, "last_pk": 35000},
    "invoice_items": {"target": 500000, "completed": 0,    "last_pk": null}
  }
}
```

Default location: `./.hyperadmin-seed.json` (cwd-relative). Override with `--state-file PATH`.
Removed on clean completion. `plan_hash` covers `(table_order, target_counts, fk_distribution,
schema_column_names_per_table)` — any drift triggers a hard abort on `--resume`.

### API / Protocol Changes

**New public exports** from `hyperadmin.loadtest`:

```python
# loadtest/plan.py
@dataclass(frozen=True)
class TablePlan:
    name: str
    target_count: int
    row_factory: Callable[[FKPool, random.Random, int], dict[str, Any]]
    fk_parents: tuple[str, ...] = ()  # parent table names; FKPool must contain these
    unique_columns: tuple[str, ...] = ()  # columns that need sequence-prefix mitigation

@dataclass(frozen=True)
class SeedPlan:
    tables: tuple[TablePlan, ...]  # order matters: parents before children

    def hash(self) -> str: ...     # sha256 over canonical JSON of the plan + schema columns
```

```python
# loadtest/pool.py
class FKPool:
    """In-memory FK ID store with Pareto-skewed sampling."""

    def __init__(self, *, pareto_a: float = 1.16, rng: random.Random | None = None) -> None: ...
    def extend(self, table: str, pks: Iterable[int]) -> None: ...
    def sample(self, table: str) -> int: ...      # Pareto-weighted draw
    def sample_many(self, table: str, n: int) -> list[int]: ...
    def __len__(self) -> int: ...                 # total IDs across all tables
    def size(self, table: str) -> int: ...
```

```python
# loadtest/batch.py
class BulkSeeder:
    def __init__(
        self,
        *,
        plan: SeedPlan,
        engine: sqlalchemy.Engine,         # sync Core engine
        batch_size: int = 5000,
        rng_seed: int = 42,
        state_file: pathlib.Path = pathlib.Path(".hyperadmin-seed.json"),
        resume: bool = False,
        progress: ProgressReporter | None = None,
    ) -> None: ...

    def run(self) -> SeedSummary: ...      # blocking; signal-handled
```

`BulkSeeder.run()` is **synchronous** by design — `insert().values(batch)` is a sync API and
async would force a thread bridge anyway. The async wrapper for `examples/erp/seed.py` runs
`BulkSeeder.run()` via `asyncio.to_thread()`.

**CLI surface** (`management/commands/seed.py`):

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--count N` | `int` | required | Total target rows across the ERP plan; per-table targets are derived proportionally from the plan. |
| `--batch-size` | `int` | `5000` | Rows per `INSERT ... VALUES (...)` batch. Auto-shrunk on SQLite to respect SQLITE_MAX_VARIABLE_NUMBER. |
| `--database-url` | `str` | env `DATABASE_URL` | SQLAlchemy URL. PostgreSQL recommended. |
| `--resume` | `flag` | `False` | Resume from `.hyperadmin-seed.json`. Aborts on plan-hash mismatch. |
| `--seed S` | `int` | `42` | RNG seed. CI uses default for reproducibility. |
| `--state-file PATH` | `Path` | `./.hyperadmin-seed.json` | Override checkpoint location (e.g. for parallel CI runs). |
| `--plan` | `str` | `erp` | Plan name; v0.7.1 supports `erp` and `auth`. |
| `--no-progress` | `flag` | `False` | Disable Rich UI (for plain CI logs). |

No changes to `Admin()`, `AdminOptions`, `HyperAdminSettings`, or any existing public API.

### Configuration Changes

**No new `Admin()` or settings parameters.** All knobs live on the CLI subcommand. This keeps
the load-test surface out of the runtime admin configuration — operators never accidentally
ship a seeder hook into production.

The only environment variable consulted is the standard `DATABASE_URL` (already used by
`examples/erp/seed.py`).

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Empty FK pool when child batch starts | Hard error at plan validation (parent must precede child). At runtime the pool is asserted non-empty before sampling — raises `EmptyPoolError` with the offending child/parent names. |
| Unique-constraint exhaustion | Each batch carries a per-batch sequence prefix (`f"{table}-{batch_no:08d}-{row_no:04d}"`) appended to Faker output for unique columns. Collisions become mathematically improbable. On the rare retryable `IntegrityError`, the batch is regenerated with a fresh prefix once; a second failure aborts. |
| Partial-batch resume | Checkpoints are written *after* each successful `commit()`. A crash mid-batch loses only that uncommitted batch — on `--resume`, the seeder re-derives the next batch from `tables[name].completed` and re-runs it. No partial commits. |
| SQLite parameter limit | SQLite caps host params at 32766 (modern) or 999 (legacy). The seeder inspects the dialect at startup and shrinks `batch_size` to `floor(limit / max_columns_in_plan)` if needed, logging the adjustment. |
| Pareto duplicates in FK references | **Expected and desired** — that is the whole point of the skew. Documented; not an error. |
| Plan-hash mismatch on `--resume` | Seeder exits 2 with a message naming the drift (e.g. "table `invoices` target changed: 100000 → 200000"). User must `rm .hyperadmin-seed.json` to start fresh — the seeder will not silently overwrite. |
| SIGINT / SIGTERM mid-run | Signal handler flushes the in-progress batch's checkpoint (if and only if its commit succeeded) and exits 130. The next `--resume` picks up cleanly. |
| numpy unavailable | `try: import numpy` falls back to `random.paretovariate(a)` — slower per-call but correct. Performance delta is logged at startup. |
| Progress UI in non-TTY (CI) | Rich auto-detects; if no TTY, the progress reporter degrades to one line per batch (`table=invoices completed=35000/100000 rate=28.4K/s`). `--no-progress` forces the plain mode. |
| Checkpoint fsync cost | Per-batch JSON write is cheap (small file), but `os.fsync` after every batch caps throughput. Compromise: write JSON every batch, `fsync` every 100 batches; signal handler also fsyncs. Recovery loses at most 100 batches × `batch_size` rows on a power-loss event — acceptable for a load-test tool. |
| Engine pool exhaustion under load | Seeder uses a single connection (single-threaded inserts); pool size is irrelevant. Documented. |
| FK pool memory ceiling | Pools store ints (~28 bytes/elem in CPython). 10M parent PKs ≈ 280 MB. Above ~50M PKs the pool is the dominant memory cost; a warning is logged. Spill-to-disk is deferred (Open Questions). |

## Migration & Backward Compatibility

**Backward compatible — no migration required.**

- `examples/erp/seed.py` keeps its existing entrypoint and superuser bootstrap. The new
  `BulkSeeder` is invoked from a new async wrapper that uses `asyncio.to_thread`; calling
  the script with no arguments still produces the demo superuser as before. `--bulk N` (or
  `python -m hyperadmin seed --count N`) opts into bulk seeding.
- `src/hyperadmin/loadtest/` is a brand-new package. No existing imports change.
- `__init__.py` exports of the top-level `hyperadmin` package are **unchanged**.
  `loadtest` is intentionally not re-exported at the top level — operators import it
  explicitly (`from hyperadmin.loadtest import BulkSeeder`).
- numpy stays out of `[project.dependencies]`. It is added to the **dev** extra so the
  fast-path is exercised in CI.
- No semver bump required.

## Open Questions

- [ ] **Sprint sequencing in v0.7.0:** should #246 land *before* or *after* #211
      (server-side pagination)? **Proposal:** ship #246 first so #211's benchmark suite has
      a 10M-row dataset to test against from day one. Otherwise #211 ends up shipping with
      hand-rolled fixtures that #246 then has to retrofit.
- [ ] **Spill-to-disk FK pools for >100M-row parents.** Above ~50M parent PKs, the in-memory
      `list[int]` becomes the dominant cost (≈1.4 GB at 50M). Options: SQLite-backed pool,
      mmap'd packed `array.array("q")`, or chunked sampling with a smaller hot subset.
      **Deferred** — revisit when v0.7.0 benchmarks demand it; not in v0.7.1 scope.
- [ ] **Auto-discovery of user models from SQLModel metadata.** v0.7.1 hard-codes the ERP
      plan. Users with custom schemas have no path beyond writing their own `SeedPlan` in
      Python. Generic discovery (introspect `SQLModel.metadata.tables`, infer FK edges,
      pick Faker generators by column type) is **deferred to v0.8** — non-trivial design,
      and we want one ERP-shaped plan to validate the architecture first.
- [ ] **Per-table target derivation from `--count N`.** Currently the plan defines fixed
      ratios (1 account : 100 invoices : 5 items/invoice). `--count` scales those ratios.
      Should we expose `--count-table accounts=10000` overrides? **Proposal:** defer to
      v0.7.2 — single `--count` covers the v0.7.0 benchmark needs.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Module location: `src/hyperadmin/loadtest/` (new top-level) | Independent of admin core; no `Admin()` coupling; easy to omit from production deploys via `[loadtest]` extra later. | Nest under `examples/` (would prevent reuse from a published wheel); nest under `core/` (pollutes the framework core with operator tooling) |
| **SQLAlchemy Core `insert().values(batch)` baseline only — no COPY fast path in v0.7.1** | ~30K/s on a developer laptop is a clean baseline that ships now and meets v0.7.1 BDD scenarios; COPY adds psycopg2-specific code, complicates rollback semantics, and is not needed unless benchmarks prove it blocks v0.7.0 scalability targets. **Revisit if benchmark shows it blocks v0.7.0 scalability targets.** | `psycopg.copy_expert` / `COPY FROM STDIN` (faster, ~200K/s, but PG-only and complicates resume); `executemany` (slower than `values()`); SQLAlchemy ORM `bulk_save_objects` (slowest, defeats the point) |
| numpy as a **soft** dependency with stdlib `random.paretovariate` fallback | Avoids forcing a 20+ MB transitive dep on every HyperAdmin install for a tool 99% of users never run. CI tests both code paths. | Hard runtime dep on numpy (rejected — bloats install); remove numpy entirely (rejected — measurable speedup at 10M+ samples) |
| Pareto distribution `a=1.16` (≈80/20 skew) | Industry-standard skew shape for "few dominant entities" datasets; matches real ERP customer/invoice ratios; well-known tail behaviour. | Zipf (similar shape, more parameters to explain); uniform (rejected — defeats the purpose) |
| FK pool: in-memory `dict[str, list[int]]` | Simplest correct data structure; supports random-index sampling in O(1); CPython int-list memory is tolerable up to ~50M entries. | DB-backed pool (slower, more code); `array.array("q")` (faster but overkill at v0.7.1 scales) |
| Resumability via JSON state file at `.hyperadmin-seed.json` | Human-readable, diff-able, no extra infra; cwd-relative is intuitive for one-off ops; `--state-file` covers parallel CI lanes. | DB-resident checkpoint table (couples to the schema being seeded); SQLite sidecar (more code, no readability benefit) |
| Checkpoint: per-batch JSON write, `fsync` every 100 batches | Per-batch write is cheap; bulk fsync gives ~100× throughput vs per-batch fsync; signal handler always fsyncs on Ctrl-C so worst-case loss is bounded by what crashed. | fsync every batch (kills throughput); fsync only on signal (loses too much on power-loss) |
| `plan_hash` validated on `--resume` | Schema drift mid-run silently corrupts results — hard abort is the only safe behaviour. Hash covers table order, targets, FK edges, and column names so any meaningful change is caught. | Trust the user (rejected — silent corruption); hash only table names (misses target / FK changes) |
| Default RNG seed = `42` | Deterministic, well-known sentinel; CI runs are byte-reproducible; users override with `--seed`. | Time-based seed (rejected — non-reproducible CI); no default (rejected — forces every user to think about it) |
| Hard-coded ERP plan in `loadtest/generators/erp.py` for v0.7.1 | Lets us validate the architecture against one realistic schema before generalizing; auto-discovery is a meaningfully different design problem. | Auto-discovery from SQLModel metadata (deferred to v0.8); user-supplied YAML plan files (deferred — adds parser surface area) |
| CLI: `hyperadmin seed --count N --batch-size 5000 --database-url URL [--resume] [--seed S] [--state-file PATH]` | One subcommand, clear flags, follows existing Typer conventions in `management/commands/`. | Standalone `hyperadmin-seed` script (rejected — splits the entry-point surface); per-table subcommands (rejected — bad ergonomics for plan-driven seeding) |
| `examples/erp/seed.py` keeps async wrapper that runs `BulkSeeder.run()` in a thread | Existing example is async (FastAPI flavour); `BulkSeeder` is sync because `insert().values()` is sync; `asyncio.to_thread` is the standard bridge with zero behavioural surprises. | Make `BulkSeeder` async (rejected — fights the SQLA Core API); rewrite `seed.py` as sync (rejected — diverges from the rest of the example) |
| `BulkSeeder.run()` is synchronous | Underlying `insert().values()` is sync; an async wrapper would only add a `to_thread` layer; keeping it sync makes signal handling and checkpoint flush trivial. | Async-first API (rejected — adds complexity for no throughput gain) |
| Soft-import Rich; degrade to plain logs without TTY | CI logs stay readable; developers get the rich UI; `--no-progress` is the explicit escape hatch. | Always-on Rich (rejected — garbled CI logs); always-plain (rejected — bad dev UX) |

### Decision Log — amendments made during implementation (2026-06-03)

| Decision | Rationale | Alternatives considered |
|---|---|---|
| FK sampling uses **inverse-transform of a bounded power law** (`q = u ** (a/(a-1))`) over the parent *rank*, not `random.paretovariate` | `paretovariate` is unbounded `[1, ∞)`; mapping it onto a finite ID list requires clamping the tail, which distorts the skew. The inverse-transform gives the documented "top 20% own ≈80%" property *exactly* (verified in `test_pool.py` on both the numpy and stdlib paths) and needs no clamping. numpy is still the soft-dep fast path for `sample_many`. | `random.paretovariate` + clamp (rejected — distorts tail); Zipf (more params, same shape) |
| `SeedPlan.scaled(n)` **reserves one row per table**, then apportions the remainder by weight | At small `--count`, a low-weight parent (e.g. `erp_accounts`) rounded to 0 rows, leaving its children unable to sample a FK (an `EmptyPoolError`). Reserving 1 row per table guarantees FK integrity at every scale; `scaled(n)` now requires `n >= len(tables)`. | Proportional-only rounding (rejected — breaks FK integrity at small N); min-1 only for parent tables (more code, same effect) |
| FK pool populated by querying parent PKs after each parent table completes (and on resume), not per-batch `RETURNING` | A plain `SELECT id` per parent table is dialect-agnostic and robust across SQLite/PostgreSQL; per-batch `RETURNING` via insertmanyvalues adds complexity for no benefit since parents always fully precede children. | `insert().returning(pk)` per batch (rejected — more fragile across dialects) |
| Resume re-runs the uncommitted batch deterministically from `completed`; no separate IntegrityError retry loop | Unique columns derive from a monotonic global `seq`, so a regenerated batch never collides with committed rows — the unique-exhaustion edge case is unreachable for the shipped plans by construction (verified in `test_batch.py`). | Per-batch IntegrityError retry with fresh prefix (deferred — unreachable for v0.7.1 plans) |
