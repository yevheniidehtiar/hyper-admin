from sqlalchemy.orm import DeclarativeMeta
from sqlmodel import SQLModel

from hyperadmin.adapters.registry import adapter_registry
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter

adapter_registry.register(SQLModel, SQLModelAdapter)
adapter_registry.register(DeclarativeMeta, SQLAlchemyAdapter)
