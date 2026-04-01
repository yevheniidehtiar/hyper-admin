"""Minimal file-upload HyperAdmin app for E2E testing.

Started by the ``upload_base_url`` fixture via uvicorn subprocess.
Registers a ``Document`` model with ``FileType`` and ``ImageType`` columns.
"""

from __future__ import annotations

import tempfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import Column
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

upload_dir = tempfile.mkdtemp(prefix="hyperadmin_e2e_uploads_")
storage = FileSystemStorage(upload_dir)

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
)


class Document(SQLModel, table=True):
    __tablename__ = "e2e_document"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    attachment: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=storage)),
    )
    cover_image: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=storage)),
    )


class DocumentAdmin(ModelAdmin):
    pass


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)

settings = HyperAdminSettings(
    create_tables=False,
    secret_key="e2e-upload-secret",
    debug=True,
)

site.register(Document, DocumentAdmin)

admin = Admin(app, engine=engine, settings=settings, storage=storage)
admin.mount(path="/admin")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
