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
production. PostgreSQL, concurrent users and page sizes above 10 were not covered by this run.

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
create and update writes, and log in once per user. `examples/erp/loadtest/baselines.py`
records a baseline and compares later runs against it.

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
