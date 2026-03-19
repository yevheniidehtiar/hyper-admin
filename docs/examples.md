# Examples

Two runnable example apps ship with HyperAdmin.

## simple_app — Basic CRUD

Shows a single-model admin with auto-discovery and async SQLite.

```python
# examples/simple_app.py
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, Field
from hyperadmin.main import Admin

engine = create_async_engine("sqlite+aiosqlite:///simple_app.db")

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str

app = FastAPI()
admin = Admin(app, engine=engine, discover_apps=["examples"])
admin.mount("/admin")
```

**Run locally:**

```bash
uv run uvicorn examples.simple_app:app --reload
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## rbac_app — Full RBAC Demo

Shows 5 related models (User, Group, UserGroup, Permission, UserPermissions) with search, sort, filters, and file/image uploads. Sample data is seeded automatically.

**Run with Docker** (recommended — zero setup):

```bash
docker compose -f examples/docker-compose.yml up --build
```

Open [http://localhost:8000/admin/](http://localhost:8000/admin/)

**Run locally:**

```bash
uv sync --all-extras
uv run uvicorn examples.rbac_app.main:app --reload
```

### Seeded data

| Entity | Values |
|--------|--------|
| Users | `admin`, `editor`, `viewer` |
| Groups | Administrators, Editors, Viewers |
| Permissions | 8 permissions (add/change/delete/view for user and group) |

### Models overview

| Model | Description |
|-------|-------------|
| `User` | Profile with avatar (image) and personal key (file) fields |
| `Group` | Named group for organizing users |
| `UserGroup` | Many-to-many join: User ↔ Group |
| `Permission` | Codename-based permission definition |
| `UserPermissions` | Many-to-many join: User ↔ Permission |

---

Next: [Frontend](frontend/overview.md)
