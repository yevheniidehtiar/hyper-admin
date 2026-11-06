"""Database URLs and the shared async engine.

pgtask's ``enqueue_in_session()`` needs the psycopg driver, so the SQLAlchemy engine uses
``postgresql+psycopg://``. pgtask itself (migrations, the worker, the dashboard) takes the plain
``postgresql://`` URL.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

#: Plain ``postgresql://`` URL. docker-compose sets it; the default is the compose database.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://hyperadmin:hyperadmin@127.0.0.1:5432/tasks"
)


def sqlalchemy_url(url: str) -> str:
    """Return ``url`` with the async psycopg driver that ``enqueue_in_session()`` requires."""
    scheme, _, rest = url.partition("://")
    if scheme in {"postgres", "postgresql"}:
        return f"postgresql+psycopg://{rest}"
    return url


engine = create_async_engine(sqlalchemy_url(DATABASE_URL))
Session = async_sessionmaker(engine, expire_on_commit=False)
