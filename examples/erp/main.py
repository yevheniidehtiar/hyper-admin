import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from examples.erp.db import engine
from examples.erp.reports.views import router as reports_router
from hyperadmin.auth.backend import SessionAuthBackend
from hyperadmin.auth.permissions import DatabasePermissionRegistry, RoleBasedPermissionChecker
from hyperadmin.auth.session import DBSessionStore
from hyperadmin.main import Admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Data seeding runs after Admin creates tables (Admin startup hook)
    # Wait for tables to be created by HyperAdmin
    import asyncio

    from examples.erp.seed import seed_db

    await asyncio.sleep(0.5)
    await seed_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="src/hyperadmin/static"), name="static")

# Custom reports router
app.include_router(reports_router)

# Auth setup
session_store = DBSessionStore(engine)
auth_backend = SessionAuthBackend(engine=engine, session_store=session_store)
permission_registry = DatabasePermissionRegistry(engine=engine)
permission_checker = RoleBasedPermissionChecker(engine=engine)

# Path to custom templates for this ERP app
base_dir = os.path.dirname(__file__)
template_dir = os.path.join(base_dir, "templates")

admin = Admin(
    app,
    engine=engine,
    discover_apps=[
        "examples.erp.contacts",
        "examples.erp.sales",
        "examples.erp.purchases",
        "examples.erp.accounting",
        "hyperadmin.auth",
    ],
    template_dirs=[template_dir],
    auth_backend=auth_backend,
    permission_checker=permission_checker,
    permission_registry=permission_registry,
    session_secret="super-secret-erp-key",
)

# Store admin on app state so custom views can access it (e.g. for templates)
app.state.admin = admin

admin.mount(path="/admin")

# Optional: Add custom report to the navigation menu
# (This is a bit hacky as it reaches into internals, but shows how it could be done)
admin.templates.env.globals["nav_items"].append(
    {"name": "Profit & Loss Report", "url": "/reports/profit-loss", "icon": "ha-icon-chart"}
)


@app.get("/")
def read_root():
    return {"message": "Go to /admin to see the ERP admin interface."}
