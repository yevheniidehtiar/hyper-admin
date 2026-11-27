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
from hyperadmin.core.settings import HyperAdminSettings

settings = HyperAdminSettings(discover_apps=["myapp", "otherapp"])
admin = Admin(app, engine=engine, settings=settings)
admin.mount("/admin")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `app` | `FastAPI` | required | The FastAPI application instance |
| `engine` | `AsyncEngine` | built-in SQLite | Async SQLAlchemy engine |
| `settings` | `HyperAdminSettings` | read from `HYPERADMIN_*` env vars | Every setting in the next table |
| `session_factory` | `async_sessionmaker` | `None` | Keyword-only. Use the host's own session factory instead of, or as well as, `engine` |
| `auth` | `ExternalAuth` | `None` | Keyword-only. Bring your own auth; see [Bring Your Own Auth](../guides/external-auth.md) |
| `auth_backend`, `permission_checker`, `permission_registry` | | `None` | Custom auth backend and permission services |
| `storage` | `StorageBackend` | `None` | Storage for file and image uploads (local or S3-compatible) |
| `otp_service` | | `None` | Email-OTP service for MFA |
| `realtime` | `RealtimeSettings` | `None` | SSE / WebSocket and pub/sub configuration; see [Realtime](../guides/realtime.md) |
| `disabled_plugins` | `Iterable[str]` | `()` | Keyword-only. Plugin names to skip, for example `["tasks"]` |
| `plugin_settings` | `Mapping[str, Mapping]` | `None` | Keyword-only. Settings for each plugin, by plugin name |
| `nav_groups` | `Iterable[NavGroup]` | `()` | Keyword-only. Sidebar sections; see [Navigation](../guides/navigation.md) |
| `rate_limiter` | `RateLimiter` | `None` | Keyword-only. A limiter shared between workers; see [Rate limiting](../guides/performance.md#rate-limiting) |
| `oauth_backend` | `OAuthBackend` | `None` | Keyword-only. "Sign in with Google / GitHub" on the built-in login page; see [OAuth Sign-In](../guides/oauth-sso.md) |

## Settings

Pass these through `HyperAdminSettings(...)`, or set them as environment variables with the
`HYPERADMIN_` prefix (for example `HYPERADMIN_CREATE_TABLES=true`). They are not `Admin()`
keyword arguments.

Settings that belong to one feature are described with it: the database pool and rate limiting
in [Performance](../guides/performance.md), `upload_dir`, `public_uploads_path`,
`storage_backend` and the `aws_*` settings in [File uploads](../guides/file-uploads.md).
`database_engine_kwargs`, `is_default_secret_key` and `tzinfo` are read-only properties derived
from the settings below, not settings; they have no environment variable.

| Setting | Type | Default | Description |
|-----------|------|---------|-------------|
| `site_title` | `str` | `"HyperAdmin"` | Admin name shown in the navbar, on the login page and in browser tab titles |
| `site_header` | `str` | `"HyperAdmin"` | Not shown by the built-in templates; custom templates can read it as the `site_header` Jinja global |
| `secret_key` | `str` | a built-in placeholder | Signs the session cookie and the CSRF tokens. Required (startup fails) when the admin has an `auth_backend` or `csrf_mode="enforce"`, unless `debug` is on; set `HYPERADMIN_SECRET_KEY` in production |
| `debug` | `bool` | `False` | Development mode: a list page re-raises database errors instead of showing the list-error banner, and the placeholder `secret_key` only logs a warning |
| `database_url` | `str` | `"sqlite+aiosqlite:///:memory:"` | Database the admin connects to when no `engine=` or `session_factory=` is passed. Pool settings are in [Performance](../guides/performance.md) |
| `register_auth_models` | `bool \| None` | `None` | Register the built-in `User`, `Group` and `Permission` admins. `None` turns them on with `auth_backend=` and off with `auth=` or no auth |
| `csrf_mode` | `"auto" \| "enforce" \| "report" \| "off"` | `"auto"` | When unsafe requests are checked for a CSRF token; see [CSRF protection](#csrf-protection) |
| `csrf_cookie_name` | `str` | `"hyperadmin_csrf"` | Name of the cookie that carries the CSRF token |
| `csrf_header_name` | `str` | `"X-CSRF-Token"` | Request header the admin's HTMX requests send the token in |
| `csrf_field_name` | `str` | `"csrf_token"` | Form field that carries the token in a plain form post |
| `csrf_trusted_origins` | `list[str]` | `[]` | Extra origins (`"https://admin.example"`) the `Origin` check accepts besides the admin's own |
| `plugins_enabled` | `bool` | `True` | Load the plugins installed under the `hyperadmin.plugins` entry point when the `Admin` is built. `False` skips discovery; plugins can still be registered by hand |
| `permissions_matrix_enabled` | `bool` | `True` | Register the permissions matrix page and its sidebar entry (built-in groups only). `False` leaves its URL unrouted (404) |
| `permissions_matrix_codename` | `str` | `"change_groups_permissions"` | Codename a non-superuser needs to open and save the permissions matrix. Lowercase letters, digits and `_` |
| `theme` | `"auto" \| "light" \| "dark"` | `"auto"` | Colour scheme. `"auto"` follows the operating system; users can still switch it in the navbar |
| `theme_preset` | `"terminal" \| "classic"` | `"terminal"` | Visual theme. `"terminal"`: near-black ground, square corners, acid-green accent, JetBrains Mono for headings, labels and buttons. `"classic"`: the earlier teal look with rounded corners. Works with every `theme` |
| `date_format` | `str` | `"%Y-%m-%d"` | Accepted but not read in this release: date values are shown as `YYYY-MM-DD` |
| `datetime_format` | `str` | `"%Y-%m-%d %H:%M:%S"` | `strftime` format of timezone-aware datetimes on list and detail pages |
| `timezone` | `str` | `"UTC"` | IANA zone (case-sensitive, for example `"Europe/Berlin"`) aware datetimes are shown and entered in |
| `concurrency_use_updated_at` | `bool` | `False` | Use an `updated_at` column as the version field of models without a `version` column, for stale-save detection. Approximate: two writes within the column's resolution can go undetected |
| `occ_render_dialog` | `bool` | `True` | On a stale save, show the HTML conflict dialog. `False` answers with a JSON 409 body, for API clients |
| `default_locale` | `str` | `"en"` | Language used when neither the language cookie nor `Accept-Language` matches a supported locale |
| `supported_locales` | `list[str]` | the 20 bundled locales | Locales the language switcher offers and `Accept-Language` is matched against |
| `locale_response_header` | `bool` | `True` | Send a `Content-Language` header with the resolved locale on every admin response |
| `discover_apps` | `list[str]` | `[]` | Packages whose `admin.py` modules are imported |
| `auto_discover` | `bool` | `False` | Register every SQLModel `table=True` model found, with smart defaults |
| `create_tables` | `bool` | `False` | Create every SQLModel table in `admin.startup()`. In demo mode (no `engine=`/`session_factory=`), tables are created automatically only for SQLite URLs. Otherwise use `admin.create_tables(scope=...)` or `hyperadmin init-db` |
| `template_dirs` | `list[str]` | `[]` | Extra Jinja2 template search paths |
| `mount_mode` | `"isolated" \| "router"` | `"isolated"` | `"isolated"` mounts the admin as a private sub-application (see below). `"router"` is the deprecated legacy mode, removed in 0.6 |
| `route_namespace` | `str` | `"hyperadmin"` | Name of the admin mount; admin route names resolve as `hyperadmin:user-list` |
| `session_cookie` | `str` | `"hyperadmin_session"` | Name of the admin's session cookie (built-in auth). Its `Path` is the admin path |
| `session_max_age` | `int` | `1209600` | Session cookie lifetime in seconds (14 days) |
| `session_same_site` | `"lax" \| "strict" \| "none"` | `"lax"` | `SameSite` attribute of the session cookie |
| `user_cache_ttl` | `int` | `0` | Seconds the signed-in user and its permission set are cached per worker (`HYPERADMIN_USER_CACHE_TTL`, 0 to 60; `0` = off). Built-in session auth and permission checker with integer user ids only. Other workers can serve a stale user for up to the TTL; see [Going to production](../guides/existing-app.md#8-going-to-production) |
| `items_per_page` | `int` | `10` | Rows a list page shows when the URL has no `page_size` parameter (`HYPERADMIN_ITEMS_PER_PAGE`). Values above 100 are capped at 100 |
| `nav_pins_max` | `int` | `20` | Most sidebar pages one user may pin (`HYPERADMIN_NAV_PINS_MAX`, at least 1). Pins need auth (built-in or `auth=`) and the `hyperadmin_nav_pin` table |
| `cookie_secure` | `"auto" \| bool` | `"auto"` | `Secure` flag for every admin cookie. `"auto"` sets it when the request scheme is https, so plain-http development and `TestClient` keep working; set `true` in production behind a TLS proxy |

## Isolated mount

`admin.mount("/admin")` builds a private FastAPI sub-application and attaches it with
`app.mount("/admin", ..., name="hyperadmin")`:

- the admin's locale, session and authentication middleware wrap admin requests only, so host
  routes get no `Content-Language` header and no admin cookie;
- the admin's static files are served from `/admin/static`, and the realtime WebSocket from
  `/admin/realtime/ws`; a host `/static` mount is left alone;
- admin routes are not in the host's `/openapi.json`, and their names are namespaced
  (`app.url_path_for("hyperadmin:user-list")`);
- the sub-application shares the host's `dependency_overrides` and `state`.

To serve your own page inside the admin (behind its login), add a route to `admin.asgi_app` after
`mount()`, and resolve admin URLs with `hyperadmin.views.urls.admin_url_for(request, name)`.

`admin.mount("/")` always uses router mode, because a sub-application mounted at the root
would shadow every host route.

Links and redirects the admin builds (login, logout, MFA, `{{ admin_prefix }}` in templates) use
the per-request admin path, so a host served under a `root_path` (for example `/api`) gets
`/api/admin/...`.

Uploaded files are served per record under the admin prefix, at
`{prefix}/{model}/{item_id}/file/{field}`, behind the admin's authentication, model and
object permissions and `get_queryset` scoping. There is no public `/uploads` mount any more;
`settings.public_uploads_path` restores one as a logged escape hatch (see
[File Uploads](../guides/file-uploads.md)).

### Admin session cookie

With built-in auth, the admin keeps its own signed session cookie, `hyperadmin_session`, with
`Path` set to the per-request admin path (`/admin`, or `/api/admin` under a host `root_path`). A
host `SessionMiddleware` keeps its own `session` cookie: logging in to the admin never writes the
admin user into it, and the host session is untouched. The locale cookie uses the same path and
`Secure` rule. In the deprecated router mode the legacy cookie (`session`, `Path=/`) is kept
unless `session_cookie` is set explicitly.

Behind a TLS-terminating proxy that the server does not trust (`forwarded_allow_ips`), the app
sees plain http, so `cookie_secure="auto"` leaves `Secure` off and logs a one-time warning. Set
`HYPERADMIN_COOKIE_SECURE=true` in production.

## CSRF protection

Every unsafe admin request (POST, PUT, PATCH, DELETE) is checked with a signed double-submit
token and an `Origin` check. `csrf_mode` (`HYPERADMIN_CSRF_MODE`) is one of:

- `"auto"` (default): enforce when the admin has an `auth_backend` or the host app has app-level
  `dependencies` (`FastAPI(dependencies=...)`). Otherwise CSRF is off.
- `"enforce"`: always reject a failed check with a 403.
- `"report"`: let failed checks through and log a `WARNING`.
- `"off"`: no check.

!!! warning "Host-managed auth must set `csrf_mode=\"enforce\"`"
    The admin cannot see authentication done by host middleware. If your app protects the admin
    with its own session cookie in a middleware, set `HYPERADMIN_CSRF_MODE=enforce`; under
    `"auto"` such an admin has no CSRF check.

Enforcing CSRF requires a real `secret_key` (`HYPERADMIN_SECRET_KEY`). The admin's CSRF cookie
follows `cookie_secure` (`HYPERADMIN_COOKIE_SECURE`): `"auto"` sets `Secure` when the effective
request scheme is https; set `true` behind a TLS-terminating proxy whose forwarded headers
uvicorn does not trust.

## API Reference

::: hyperadmin.core.app.Admin

---

Next: [Views](views.md)