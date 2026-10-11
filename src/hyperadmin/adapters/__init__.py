from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

from hyperadmin.adapters.introspection import datetime_kind as introspect_datetime_kind
from hyperadmin.adapters.introspection import introspect_primary_key
from hyperadmin.adapters.registry import adapter_registry
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter

__all__ = [
    "SQLAlchemyAdapter",
    "SQLModelAdapter",
    "adapter_registry",
    "introspect_datetime_kind",
    "introspect_primary_key",
]

adapter_registry.register(SQLModel, SQLModelAdapter)
adapter_registry.register(DeclarativeMeta, SQLAlchemyAdapter)
