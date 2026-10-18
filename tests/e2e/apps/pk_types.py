"""Primary-key-type and timezone fixture app for E2E testing.

Started by the ``pk_types_base_url`` fixture via a uvicorn subprocess, with
``HYPERADMIN_TIMEZONE=Europe/Amsterdam``. A dedicated app keeps the
``examples/simple`` visual baselines stable (BYOA SDD, BDD scenarios: Keys,
Datetimes).

Registered models:

* ``Document`` — ``uuid.UUID`` primary key (``default_factory=uuid4``) with
  ``list_editable = ["title"]``.
* ``Country`` — natural ``str`` primary key ``code`` with no default.
* ``Product`` — classic auto-increment ``int`` primary key.
* ``Event`` — timezone-aware ``starts_at`` column, stored as naive UTC.

``GET /_test/events`` (host route, outside the admin) returns what the
database actually holds for every ``Event``, so tests can assert the stored
UTC value rather than what the admin renders.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import FastAPI
from sqlalchemy import Column, DateTime, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import Dialect

_db_path = os.path.join(tempfile.mkdtemp(prefix="hyperadmin_e2e_pk_types_"), "app.db")
engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


class UTCStoredDateTime(TypeDecorator[datetime]):
    """Store aware datetimes as naive UTC; read them back as aware UTC.

    ``hyperadmin_tz_aware = True`` tells HyperAdmin the column is aware (SDD
    A.2 rule 2), so form input is localised from the display timezone.
    """

    impl = DateTime(timezone=False)
    cache_ok = True
    hyperadmin_tz_aware = True

    @property
    def python_type(self) -> type[datetime]:
        return datetime

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Any | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Document(SQLModel, table=True):
    __tablename__ = "e2e_pk_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1)


class Country(SQLModel, table=True):
    __tablename__ = "e2e_pk_country"

    code: str = Field(primary_key=True)
    name: str = Field(min_length=1)


class Product(SQLModel, table=True):
    __tablename__ = "e2e_pk_product"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1)


class Event(SQLModel, table=True):
    __tablename__ = "e2e_pk_event"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(min_length=1)
    starts_at: datetime = Field(sa_column=Column(UTCStoredDateTime(), nullable=False))


class DocumentAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    list_editable: ClassVar[list[str]] = ["title"]


class CountryAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class ProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class EventAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


async def _seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        session.add_all(
            [
                Document(title="Alpha"),
                Document(title="Beta"),
                Country(code="FR", name="France"),
                Product(name="Widget"),
            ]
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await _seed()
    yield


app = FastAPI(lifespan=lifespan)

settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-pk-types-secret",
    debug=True,
)

site.register(Document, DocumentAdmin)
site.register(Country, CountryAdmin)
site.register(Product, ProductAdmin)
site.register(Event, EventAdmin)

admin = Admin(app, engine=engine, settings=settings)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/_test/events")
async def stored_events() -> list[dict[str, str]]:
    """Return each Event's ``starts_at`` exactly as the database holds it."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT title, starts_at FROM e2e_pk_event ORDER BY id"))
        return [{"title": row[0], "starts_at": str(row[1])} for row in result]
