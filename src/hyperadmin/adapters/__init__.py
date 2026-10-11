from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

from hyperadmin.adapters.registry import adapter_registry
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter

# Primary-key / datetime-kind introspection (hyperadmin.adapters.introspection) is
# consumed through BaseAdapter.pk / BaseAdapter.datetime_kind() per the SDD, not
# re-exported here — the adapters above import it directly.

__all__ = [
    "SQLAlchemyAdapter",
    "SQLModelAdapter",
    "adapter_registry",
]

adapter_registry.register(SQLModel, SQLModelAdapter)
adapter_registry.register(DeclarativeMeta, SQLAlchemyAdapter)
