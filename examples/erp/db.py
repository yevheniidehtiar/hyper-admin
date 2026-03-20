import os

from sqlalchemy.ext.asyncio import create_async_engine

DB_URL = (
    "sqlite+aiosqlite:///:memory:"
    if os.environ.get("E2E_TESTING")
    else "sqlite+aiosqlite:///erp.db"
)

engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})
