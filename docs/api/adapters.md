# Adapters

Adapters translate between a data source (SQLModel, SQLAlchemy, or custom) and HyperAdmin's view layer.

## Built-in Adapters

| Adapter | Module | Works with |
|---------|--------|------------|
| `SQLModelAdapter` | `hyperadmin.adapters.sqlmodel` | SQLModel async models |
| `SQLAlchemyAdapter` | `hyperadmin.adapters.sqlalchemy` | SQLAlchemy async models |

HyperAdmin auto-selects the right adapter at registration time via the adapter registry.

## Writing a custom adapter

Subclass `BaseAdapter` and implement all abstract methods:

```python
from hyperadmin.core.adapters import BaseAdapter

class MyAdapter(BaseAdapter):
    async def get(self, pk):
        ...

    async def list(self, page=1, page_size=10, search=None, filters=None, order_by=None):
        # Return (items, total_count)
        ...

    async def create(self, data):
        ...

    async def update(self, pk, data):
        ...

    async def delete(self, pk):
        ...

    async def get_related(self, pk, field):
        ...

    async def get_schema(self):
        ...
```

`filters` is either a legacy `{column: value}` equality dict or a
`Sequence[FilterCondition]` (`hyperadmin.core.filtering`). Call
`hyperadmin.core.filtering.normalize_filters(filters)` to always get
`list[FilterCondition]` (ops: exact/gte/lte/in/isnull) before building your
query.

Register it with `adapter_registry` so HyperAdmin can discover it automatically:

```python
from hyperadmin.adapters.registry import adapter_registry
adapter_registry.register(MyModel, MyAdapter)
```

### Inline formsets and row scoping

If your adapter supports inline formsets (it implements `save_inline_rows`), it
must also implement `inline_child_pks(spec, parent_pk)` and return the primary
keys of the `spec.model` rows whose `spec.fk_field` equals `parent_pk`. Before
any write, HyperAdmin checks that every submitted inline row pk is one of those
keys. The default implementation returns an empty set, so without an override
every save of a parent that has existing inline rows is rejected with 404.

Row scoping from `ModelAdmin.get_queryset` reaches adapters through
`self._resolve_queryset_filters()` (for the adapter's own model) and
`hyperadmin.core.adapters.scoped_queryset_filters(model)` (for related models,
for example in `get_choices`). Apply both as equality filters on every read.

### Applying list filters in your own query

A plugin or a custom view that queries a model itself (a report, an export) can apply the same
filters the list page applies. `FilterDef.compile` turns a filter's querystring into typed
`FilterCondition` objects, and `build_clauses` turns those into SQLAlchemy clauses for a
SQLModel or SQLAlchemy model:

```python
from sqlmodel import select

from hyperadmin.adapters.filtering import build_clauses

statement = select(Order).where(*build_clauses(Order, conditions))
```

`build_clauses` lives under `hyperadmin.adapters` because `hyperadmin.core` imports no ORM.

## API Reference

::: hyperadmin.adapters.filtering.build_clauses

::: hyperadmin.core.adapters.BaseAdapter

::: hyperadmin.adapters.sqlmodel.SQLModelAdapter

::: hyperadmin.adapters.sqlalchemy.SQLAlchemyAdapter