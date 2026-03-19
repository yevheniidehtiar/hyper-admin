import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

# DATABASE_URL can be overridden via environment variable.
# Docker sets it to a named volume path; local dev defaults to a file in cwd.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./rbac_app.db")

# Extract the raw file path for sqlite:/// URLs (used to create parent dirs).
SQLITE_PATH = DATABASE_URL.split(":///", 1)[1] if ":///" in DATABASE_URL else ""

# Sync engine — used only for table creation and seeding at startup.
sync_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Async engine — used by HyperAdmin adapters at runtime.
_async_url = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
engine = create_async_engine(_async_url)
