# hyperadmin-logfire

First-party HyperAdmin plugin that sends admin traces to [Pydantic Logfire](https://logfire.pydantic.dev).

## Install

The plugin is not on PyPI yet. Install it from the repository:

```bash
uv add "hyperadmin-logfire @ git+https://github.com/yevheniidehtiar/hyper-admin#subdirectory=plugins/hyperadmin-logfire"
```

## Use

Configure Logfire as usual, then call `instrument_admin` after `admin.mount()`:

```python
import logfire
from hyperadmin import Admin
from hyperadmin_logfire import instrument_admin

logfire.configure()  # your token, environment, scrubbing and sampling live here

admin = Admin(app, engine=engine)
admin.mount("/admin")
instrument_admin(admin)
```

You get a span per admin request with its SQL queries nested under it. `instrument_admin` is
idempotent and does nothing when the plugin is disabled (`disabled_plugins=["logfire"]` or
`HYPERADMIN_DISABLED_PLUGINS=logfire`). Until `logfire.configure()` runs, Logfire records nothing
and warns once.

## What works on which versions

| | FastAPI with native telemetry (0.143+) | Older FastAPI (from 0.116) |
|---|---|---|
| HTTP spans | FastAPI's own, route `/admin/product` | `logfire.instrument_fastapi` on the admin sub-app, route `/product` (full path in `http.target`) |

| | SQLAlchemy 2.0 | SQLAlchemy 2.1 |
|---|---|---|
| SQL spans | `logfire.instrument_sqlalchemy` | the plugin's built-in spans (same names and `db.*` attributes); `opentelemetry-instrumentation-sqlalchemy` does not support 2.1 yet |

- **FastAPI with native telemetry** traces every app once `logfire.configure()` has run, not
  only the admin, and whether or not the plugin is enabled. The plugin leaves those spans alone:
  `logfire.instrument_fastapi` would replace them with coarser ones and silence FastAPI's native
  spans for the whole process. To turn them off: `FastAPI(telemetry={"tracing": False})`.
- **Legacy router mode** (`mount_mode="router"`): the admin routes live on the host app, so on
  older FastAPI the plugin instruments the host app.
- **Several admin engines in one process:** the OpenTelemetry instrumentor handles one engine
  per process; every further admin engine gets the built-in spans.
- **Already instrumenting yourself?** If your app called `logfire.instrument_sqlalchemy()` first,
  the plugin leaves SQLAlchemy to it. Pass `http=False` or `sql=False` to opt out explicitly.
- **Admin built from a `session_factory` only?** There is no engine to instrument; call
  `logfire.instrument_sqlalchemy(engine=...)` on your own engine.

Adapter spans (`admin.adapter.<op>`) and validation/auth events follow once core fires the
lifecycle hooks. See `docs/specs/plugin-logfire.md`.
