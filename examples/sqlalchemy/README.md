# SQLAlchemy example

HyperAdmin on a plain SQLAlchemy 2.0 `DeclarativeBase` (no SQLModel). Models are registered
explicitly with `site.register(...)` in `admin.py`; HyperAdmin builds each model's form and
list schema from its mapper (`hyperadmin.core.schema_for`).

## Boot

```bash
uv sync --all-extras
uv run uvicorn examples.sqlalchemy.main:app    # http://127.0.0.1:8000/admin
```

The first run creates `sqlalchemy_app.db` in the working directory; delete it to start over.

## What to look at

| Column kind | Where |
|---|---|
| Enum (`SAEnum`) | Projects -> `status` select |
| Enum via `TypeDecorator` + `Mapped[Priority]` | Projects -> `priority` select |
| JSON | Projects -> `payload` textarea |
| Nullable string | Projects -> `note` (optional) |
| FK relation | Projects -> `org_id` select |
| `server_default` timestamp | `created_at`, filled by the database |
| Sensitive column | Orgs -> `api_token` (hidden on detail, write-only in forms) |
