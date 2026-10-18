# Bring your own auth

`Admin(auth=ExternalAuth(...))` lets HyperAdmin reuse your application's own
authentication: your user model, your login page, your tokens and your
permissions. In this mode the admin has no login page of its own (unless you
ask for one), no `hyperadmin_*` tables and no session middleware.

This page is the reference. For the end-to-end walkthrough, start with
[Add HyperAdmin to an existing FastAPI app](existing-app.md).

```python
from hyperadmin import Admin
from hyperadmin.auth import ExternalAuth

admin = Admin(
    app,
    session_factory=sessionmaker,
    auth=ExternalAuth(get_user=get_current_user, login_url="/login", logout_url="/"),
)
admin.mount("/admin")
```

## `ExternalAuth` options

| Option | Default | Meaning |
|---|---|---|
| `get_user` | required | Any FastAPI dependency. Returns the current user, or `None` when the request is anonymous. |
| `can_access(user)` | `is_superuser` or `is_staff` is truthy | Whether a signed-in user may open the admin at all. Sync or async. |
| `has_permission(user, codename)` | `None` | Your permission model. A callable (sync or async) or an object with `has_permission`/`get_user_permissions`. See [Permissions](#permissions). |
| `allow_full_access` | `False` | Without `has_permission`: give every user who passes `can_access` full access, not only superusers. Logs a startup warning. |
| `login_url` | `None` | Where to send an anonymous browser. The admin appends `?next=<admin path>`. |
| `logout_url` | `None` | Where the admin's logout button redirects after clearing its cookie (`/` when unset). |
| `next_param` | `"next"` | Name of the query parameter carrying the return path. |
| `display_name(user)` | `username`, then `email`, then `name` | The name shown in the navbar. Must be sync. |
| `user_key(user)` | `user.id` | A hashable key for the user (realtime connections, logs). Must be sync. |
| `token_cookie` | `None` | `TokenCookie(...)` for bearer-only hosts. See [Bearer-token hosts](#bearer-token-hosts). |
| `websocket_user(websocket)` | `None` | Async function resolving the user of a realtime WebSocket. See [Realtime](#realtime). |

On every admin request the admin sets `request.state.user`,
`request.state.user_key` and `request.state.user_display`, so your
`ModelAdmin.get_queryset(request)` and object-permission checkers receive your
own user object.

## How `get_user` runs

`get_user` is attached as a route dependency of every admin route, so FastAPI
resolves it exactly as it does on your own routes:

- its sub-dependencies (`OAuth2PasswordBearer`, `get_db`, `Security` scopes) run;
- `yield` dependencies and sync functions work;
- `app.dependency_overrides[get_user]` in your tests applies under `/admin`;
- `request.app.state` is your app's state: the admin sub-application shares it.

It must resolve from headers and cookies alone. A dependency that needs a query
or path parameter makes every admin page answer 422.

An `OAuth2PasswordBearer(auto_error=True)` that raises 401 is fine: the admin
treats that 401 as "anonymous". Prefer `auto_error=False` and return `None`,
which makes the intent explicit.

## Anonymous and denied requests

| Situation | Browser page | HTMX request | API path (`/realtime/...`, the token handoff) |
|---|---|---|---|
| No user, `login_url` set | 303 to `login_url?next=...` | 401 with `HX-Redirect` | 401 |
| No user, `TokenCookie(token_endpoint=...)` and no `login_url` | 303 to `/admin/login?next=...` | 401 with `HX-Redirect` | 401 |
| No user, neither set | 401 page "Sign in to the host application" | 401 with `HX-Refresh: true` | 401 |
| User fails `can_access` (or your dependency raises 403) | 403 page naming `can_access` | 403 | 403 |
| User lacks a model or object permission | The admin's normal 403 page | 403 | 403 |

The `next` value is built on the server from the current admin path; it never
comes from user input.

## Permissions

The admin asks for codenames of the form `<action>_<model>`, where `<model>` is
the lowercased model class name: `view_project`, `add_project`,
`change_project`, `delete_project`, and `action_<name>` for custom actions.

The permission checker is chosen in this order:

1. `Admin(permission_checker=...)`, when you pass one.
2. `ExternalAuth(has_permission=...)`.
3. The **fail-safe default**: a user with a truthy `is_superuser` gets every
   permission; every other user gets `view_*` only. `allow_full_access=True`
   gives everyone who passes `can_access` every permission.

Whatever the checker, a user who is not a superuser never gets `change_*` or
`delete_*` on **your user model** (the class of the object `get_user`
returns) unless your own `has_permission` grants it. A staff user cannot make
themselves a superuser through the admin.

```python
def has_permission(user: Account, codename: str) -> bool:
    if user.is_superuser:
        return True
    action, _, model = codename.partition("_")
    return model in {"project", "country"} and action in {"view", "add", "change"}


auth = ExternalAuth(get_user=get_current_user, has_permission=has_permission)
```

`ModelPermissionChecker` (the built-in, table-backed checker) can only be
combined with `auth=` when `HYPERADMIN_REGISTER_AUTH_MODELS=true`: it reads the
`hyperadmin_*` tables, keyed on integer user ids. Otherwise `Admin(...)` raises
`ValueError`.

## Cookie-based hosts

If your app signs users in with a cookie (a server-side session, a signed
cookie), there is nothing more to do: the browser sends that cookie to `/admin`
too, and `get_user` reads it. HyperAdmin never writes a cookie named `session`.

## Bearer-token hosts

A browser that navigates to `/admin` sends no `Authorization` header. With
`token_cookie=TokenCookie()`, the admin keeps the bearer token in its own
`hyperadmin_token` cookie (`HttpOnly`, `SameSite=Lax`, `Path=/admin`, `Secure`
per `cookie_secure`) and turns it back into an `Authorization` header on every
admin request. An explicit `Authorization` header always wins over the cookie.

There are two ways to get the token into the cookie.

### Option 1: hand the token over (SPAs)

Your frontend already holds the token. Post it once to the admin:

```javascript
await fetch("/admin/auth/session", {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
});
location.assign("/admin/");
```

`POST /admin/auth/session` runs your `get_user` on that header. It returns 204
and sets the cookie, or 303 to a validated `?next=` path inside the admin. It
returns 401 when your dependency rejects the token (no cookie is set) and 400
for a token over 3,800 bytes, which would not fit in a cookie. It needs no CSRF
token: a cross-site page cannot set an `Authorization` header.

`examples/byoa/login.html` is a complete login page built this way.

### Option 2: let the admin serve a login form

When you do not want to change your frontend at all, give the admin your token
endpoint:

```python
from hyperadmin.auth import ExternalAuth, TokenCookie

auth = ExternalAuth(
    get_user=get_current_user,
    token_cookie=TokenCookie(token_endpoint="/token"),
)
```

The admin then serves a CSRF-protected form at `/admin/login`. It posts the
credentials **server side** as an OAuth2 password grant
(`grant_type=password&username=...&password=...`) and expects a JSON
`access_token` back. `token_endpoint` can be:

- a path on your app, such as `"/token"`, called in process (no network round trip);
- an absolute `http(s)://` URL;
- `"auto"`: the `tokenUrl` of the `OAuth2PasswordBearer` found in `get_user`'s dependencies;
- a callable `issue_token(username, password) -> str | None`, sync or async.

Without `login_url`, anonymous browsers are sent to this form.

### Cookie lifetime

The cookie's `Max-Age` is the smaller of `TokenCookie.max_age` (8 hours by
default) and the time left before the JWT's `exp` claim. The claim is read
without verifying the signature, only to size the cookie: your dependency still
verifies the token on every request. There is no refresh. When your dependency
rejects a token that came from the cookie, the admin clears the cookie before
redirecting to the login page, so an expired token never causes a login loop.

## Logout

`POST /admin/logout` (the navbar's logout button) clears `hyperadmin_token`
and redirects to `logout_url`, or `/`. It does not sign the user out of your
app; point `logout_url` at your own logout page for that.

## Realtime

With `Admin(realtime=RealtimeSettings(...))`, the SSE endpoint works with any
`get_user`. HTTP dependencies do not run on a WebSocket, so the WebSocket route
is registered only when you pass `websocket_user`:

```python
async def websocket_user(websocket: WebSocket) -> Account | None:
    token = websocket.cookies.get("hyperadmin_token")
    claims = decode_token(token) if token else None
    return await load_account(claims["sub"]) if claims else None


auth = ExternalAuth(get_user=get_current_user, websocket_user=websocket_user)
```

The user must still pass `can_access`, and a handshake from a foreign `Origin`
is refused.

Realtime connections are drained only by `admin.shutdown()`, so realtime users
must compose the admin's lifespan into their own:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with admin.lifespan():
        yield
```

## Constraints

- `auth=` cannot be combined with `auth_backend=` or `otp_service=` (built-in
  auth and MFA): `Admin(...)` raises `ValueError`.
- CSRF is enforced in this mode, so `HYPERADMIN_SECRET_KEY` must be set (or
  `HYPERADMIN_DEBUG=true` during development).
- The built-in `User`, `Group` and `Permission` admins are not registered. Set
  `HYPERADMIN_REGISTER_AUTH_MODELS=true` if you want them anyway.
