import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from examples.rbac_app.create_sample_data import create_sample_data, create_tables
from examples.rbac_app.db import SQLITE_PATH, engine
from examples.rbac_app.admin import (
    GroupAdmin,
    PermissionAdmin,
    UserAdmin,
    UserGroupAdmin,
    UserPermissionsAdmin,
)
from hyperadmin import Admin


@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Cleanup old db
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
    # create sample data
    create_tables()
    create_sample_data()

    yield
    # Remove existing database if it exists
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)


# Create FastAPI app
app = FastAPI(
    title="SQLAdmin Demo",
    description="Demo application showcasing SQLAdmin with HTMX",
    lifespan=lifespan,
)

# Create admin interface
admin = Admin(app, engine, title="Demo Admin", base_url="/admin")


# Add views to admin
admin.add_view(UserAdmin)
admin.add_view(GroupAdmin)
admin.add_view(UserGroupAdmin)
admin.add_view(PermissionAdmin)
admin.add_view(UserPermissionsAdmin)


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
