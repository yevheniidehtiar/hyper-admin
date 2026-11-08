# Large Tables and Performance

The defaults suit small and medium databases. When a table grows to millions of rows, or a model
has many relations, a handful of options keep the list, form and filter pages fast. Each one is
set per model on `AdminOptions`:

```python
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions


class OrderAdmin(ModelAdmin):
    options = AdminOptions(
        list_select_related=["customer"],
        count_cache_ttl=30,
        count_estimate_threshold=1_000_000,
        preload_threshold=500,
        filter_cache_ttl=60,
    )
```

## Relations on list pages

A list page loads only the relations it shows. Every relation named in `column_list`, either on
its own (`"customer"`) or through a dotted accessor (`"customer.name"`), is loaded with one
`SELECT ... IN (...)` for the page. Other relations are not loaded, which saves one query per
relation on every request.

| Option | Default | Effect |
|---|---|---|
| `list_select_related` | `None` | Extra relations to load on the list page. |
| `auto_select_related` | `True` | Load the relations named in `column_list`. `False` loads only `list_select_related`. |
| `detail_select_related` | `None` | Relations on the detail page. `None` loads every relation; `[]` loads none. |

!!! warning "Upgrading from 0.6"
    Before 0.7, a list page loaded every relation of the model. A custom list template, or a
    `__str__` that reads a relation, which is not in `column_list` now fails with
    `DetachedInstanceError`. Name the relation in `list_select_related`:

    ```python
    options = AdminOptions(list_select_related=["customer", "warehouse"])
    ```

    Detail pages are unchanged unless you set `detail_select_related`.

Adapters take the same list as a `load_relations` argument on `list()` and `get()`. An unknown
relation name raises `ValueError`.

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

## Foreign-key fields

A foreign key to a small table renders as a select with every option in the page. A foreign key
to a large table would make the form slow to load, so at `preload_threshold` rows (default 500)
the field becomes an autocomplete that fetches matches as the user types. The row count is the
same cheap estimate as above. Set `preload_threshold=None` to always preload, which is how 0.6
behaved. An adapter that cannot estimate keeps preloading.

## List filters

Each foreign-key filter in `list_filter` lists the first rows of its related table.
`filter_cache_ttl` (default 60 seconds, `0` to disable) reuses those rows between renders and
drops them when the related model is written through its adapter.

Filter caches hold up to 1000 choices per filter, so they are the largest cache. Plan for roughly
a hundred kilobytes per cached filter and a few megabytes per worker on a typical admin. Every
worker process keeps its own copy.
