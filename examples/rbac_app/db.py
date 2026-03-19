import os

from sqlalchemy import create_engine

# DATABASE_URL can be overridden via environment variable.
# Docker sets it to a named volume path; local dev defaults to a file in cwd.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./rbac_app.db")

# Extract the raw file path for sqlite:/// URLs (used to create parent dirs).
SQLITE_PATH = (
    DATABASE_URL.removeprefix("sqlite:///") if DATABASE_URL.startswith("sqlite:///") else ""
)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
