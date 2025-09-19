# Application

API reference for the Application object.

## `Admin` Class

The `Admin` class is the main entry point for the admin interface.

### `__init__`

```python
def __init__(
    self,
    app: FastAPI,
    discover_apps: list[str] | None = None,
    create_tables: bool = True,
    engine: Any = None,
)
```

**Parameters:**

- `app` (FastAPI): The FastAPI application instance.
- `discover_apps` (list[str] | None): A list of app modules to discover admin modules from.
- `create_tables` (bool): If `True`, creates the database tables on startup.
- `engine` (Any | None): The database engine to use. If `None`, the default engine will be used.

## `site.register`

The `site.register` method is used to register a model with the admin interface.

### `register`

```python
def register(
    self,
    model: Any,
    admin_class: Any = None,
    options: AdminOptions = None,
) -> None
```

**Parameters:**

- `model` (Any): The model class or instance to register.
- `admin_class` (Any | None): The admin class to associate with the model. If `None`, `ModelAdmin` will be used.
- `options` (AdminOptions | None): The admin options to associate with the model. If `None`, default options will be used.
