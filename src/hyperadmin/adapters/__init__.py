from sqlalchemy.orm import DeclarativeBase, DeclarativeBaseNoMeta, DeclarativeMeta
from sqlmodel import SQLModel

from hyperadmin.adapters.registry import adapter_registry
from hyperadmin.adapters.schema import build_sqlalchemy_schema, is_sqlalchemy_mapped
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.schema import schema_registry

# Primary-key / datetime-kind introspection (hyperadmin.adapters.introspection) is
# consumed through BaseAdapter.pk / BaseAdapter.datetime_kind() per the SDD, not
# re-exported here — the adapters above import it directly.

__all__ = [
    "SQLAlchemyAdapter",
    "SQLModelAdapter",
    "adapter_registry",
]

adapter_registry.register(SQLModel, SQLModelAdapter)
# SQLAlchemy 2.0 declarative bases are matched through the model's MRO; legacy
# ``declarative_base()`` models through their ``DeclarativeMeta`` metaclass.
adapter_registry.register(DeclarativeBase, SQLAlchemyAdapter)
adapter_registry.register(DeclarativeBaseNoMeta, SQLAlchemyAdapter)
adapter_registry.register(DeclarativeMeta, SQLAlchemyAdapter)

# Plain SQLAlchemy models have no ``model_fields``; their schema is built from the mapper.
schema_registry.register(is_sqlalchemy_mapped, build_sqlalchemy_schema)
