import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from examples.rbac_app.create_sample_data import create_sample_data, create_tables
from examples.rbac_app.db import SQLITE_PATH, engine
from hyperadmin import Admin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rbac_app")


@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Ensure parent directory exists (needed when DATABASE_URL points to a volume path)
    if SQLITE_PATH:
        db_dir = os.path.dirname(SQLITE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    # Create tables and seed sample data (idempotent — skips if data exists)
    create_tables()
    create_sample_data()

    yield


# Create FastAPI app
app = FastAPI(
    title="SQLAdmin Demo",
    description="Demo application showcasing SQLAdmin with HTMX",
    lifespan=lifespan,
    debug=True,
)

# Add session middleware for authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET_KEY", "temporary-secret-key-for-dev"),
)

# Create admin interface — discover admin.py from the rbac_app package
admin = Admin(app, engine=engine, create_tables=False, discover_apps=["examples.rbac_app"])
admin.mount("/admin")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %d %.1fms", request.method, request.url.path, response.status_code, elapsed_ms
    )
    return response


@app.get("/")
async def root():
    """Root endpoint with links to admin."""
    return {
        "message": "Welcome to SQLAdmin Demo!",
        "admin_url": "/admin",
        "docs_url": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
