# rbac_app — HyperAdmin RBAC Example

A full-featured example showing 5 related models with search, sort, filters, and file uploads.

## Quick start (Docker)

From the repo root:

```bash
docker compose -f examples/docker-compose.yml up --build
```

Open http://localhost:8000/admin/

Data is seeded automatically on first startup and persists in a named Docker volume across restarts.

## Seeded data

| Entity | Values |
|--------|--------|
| Users | `admin`, `editor`, `viewer` |
| Groups | Administrators, Editors, Viewers |
| Permissions | 8 permissions (add/change/delete/view for user and group) |

## Models

| Model | Description |
|-------|-------------|
| `User` | User with profile, avatar (image upload), and personal key (file upload) |
| `Group` | Named group for organizing users |
| `UserGroup` | Many-to-many join between User and Group |
| `Permission` | Codename-based permission definition |
| `UserPermissions` | Many-to-many join between User and Permission |

## Local development (without Docker)

```bash
uv sync --all-extras
uv run uvicorn examples.rbac_app.main:app --reload
```

Open http://localhost:8000/admin/
