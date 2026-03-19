# Application

## Usage

```python
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from hyperadmin import Admin

app = FastAPI()
engine = create_async_engine("sqlite+aiosqlite:///app.db")

# Minimal setup — register models manually then mount
admin = Admin(app, engine=engine)
admin.mount("/admin")

# Auto-discover admin.py files in your app packages
admin = Admin(app, engine=engine, discover_apps=["myapp", "otherapp"])
admin.mount("/admin")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | `FastAPI` | required | The FastAPI application instance |
| `engine` | `AsyncEngine` | built-in SQLite | Async SQLAlchemy engine |
| `discover_apps` | `list[str] \| None` | `None` | Module paths to auto-discover `admin.py` in |
| `create_tables` | `bool` | `True` | Auto-create DB tables on startup |
| `template_dirs` | `list[str] \| None` | `None` | Extra Jinja2 template search paths |

## API Reference

::: hyperadmin.core.app.Admin

---

Next: [Views](views.md)