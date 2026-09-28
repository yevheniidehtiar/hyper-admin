# SDD: Bring Your Own App (BYOA)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | _TBD. Tracked in `.meta/epics/epic-v058-bring-your-own-app/`_ |
| Milestone | v0.5.8 — Bring Your Own App (dogfood-1) |
| Created | 2026-09-28 |
| Last updated | 2026-09-28 |

**Rules applied:** the Rippletide hook returned none. This SDD follows CONSTITUTION.md §1 (`core/` holds contracts with no ORM or HTTP code), §2 (dependencies point inward), §3 (banned file names), §4 (public API is additive and opt-in), §5 (new features go in new modules) and §6 (each runtime dependency is justified). It also follows `.claude/rules/sdd-conventions.md`, `bdd-conventions.md` (one behaviour per scenario) and `planning-playbook.md` (stories ordered bottom-up), plus the E2E selector convention in CLAUDE.md (`data-testid` tokens stay unchanged for int keys).

**Baseline:** all `file:line` references point to `origin/fix/restore-green-develop` @ `f96dcc0`, which is `origin/develop` @ `30f58d5` plus the CI fix. That fix deletes the orphan `auth/oauth/backend.py`, caps `sqlmodel<0.0.45` and fixes the inline-editor Escape race. Implementation branches start from that commit (or from `develop` once it is merged).

---

> ### Owner decisions needed
>
> Each item below has a recommended default. If a decision is not recorded, the SDD proceeds with that default.
>
> 1. **Default mount mode.** The admin becomes an isolated sub-application (`mount_mode="isolated"`). As a result:
>    - `/static` and `/uploads` move under `/admin/`;
>    - route names become `hyperadmin:*`;
>    - the session cookie is renamed, so every user logs in once more.
>
>    **Recommended:** `isolated` is the default, and `mount_mode="router"` stays available with a `DeprecationWarning` for one release (it is removed in 0.6).
> 2. **Rolling out CSRF to existing built-in-auth apps.** Two options: enforce immediately, or run report-only for one release.
>    **Recommended:** enforce immediately. `HYPERADMIN_CSRF_MODE=report` is the escape hatch, documented in the upgrade note. Every template that extends `_base.html` is covered automatically. Only custom raw `<form method="post">` templates and scripts need changes.
> 3. **Bridge-mode permissions when `has_permission` is omitted.** Two options: full access for every user who passes `can_access`, or view-only.
>    **Recommended:** full access, plus a startup `WARNING` naming the setting. `can_access` is already deny-by-default (it requires `is_staff` or `is_superuser`), and view-only would break the 10-minute goal.
> 4. **The authorization gaps are live today.** Inline edit/save, the update form, file delete and single-row actions skip object-level checks, and inline edit/save also skips model-level checks.
>    **Recommended:** ship story `st-v058-byoa-10` as a standalone `fix(views)` PR now, without waiting for this SDD's approval. Bug fixes need no SDD under sdd-conventions.
> 5. **PyPI release.** The distribution name is `hyper-admin` and the import name is `hyperadmin`. The first release is the pre-release `0.5.0a1`, published with trusted publishing from GitHub environment `pypi`.
>    **Owner action:** confirm the name is available on PyPI, and configure the trusted publisher before story `st-v058-byoa-50` merges.
> 6. **Existing `hyperadmin_*` timestamps.** Built-in auth rows were written with naive local `datetime.now()`. After this change they are read back as UTC, so on servers that do not run in UTC the displayed `created_at` shifts.
>    **Recommended:** accept this and add a release note. No data-fix command.
> 7. **URL filters restricted to `list_filter`.** Today any `filter_<column>=` query parameter is accepted, which lets anyone test equality on secret columns such as `password_hash`.
>    **Recommended:** accept only fields named in `list_filter`, and ignore the rest. Record this in the changelog as a security fix.

---

## Problem

HyperAdmin today assumes it owns the application it is mounted into. A developer with an **existing** FastAPI app — SQLModel models, UUID or natural-string primary keys, Alembic migrations, and their **own** authentication (JWT or OAuth2 bearer, their own user model) — cannot add the admin without it taking over the app, and in several cases cannot add it at all.

| # | Blocker | Evidence |
|---|---|---|
| B1 | **Only integer primary keys work.** A UUID or `str` key gets a 404 on every item route. On SQLite, binding a raw path string to a UUID column raises a 500. | `routing.py:105-202` `{item_id:int}`; `adapters/sqlmodel.py:43,189` `self.model.id`; `views/dynamic.py:329,364,775,1321`, choices, inline rows and templates use `item.id` |
| B2 | **There is no way to plug in the host app's own auth.** The only option is `Admin(auth_backend=…)`, which brings username/password login, app-wide middleware and always-on `User`/`Group`/`Permission` admins. | `core/app.py:340-355,416-448`; `auth/middleware.py:67` |
| B3 | **Packaging is incomplete.** `pydantic-settings` is imported but not declared as a dependency. `db.py` creates an engine when imported. `appnope` is a stray runtime dependency. There is no committed `uv.lock`, and the package has never been published to PyPI. | `pyproject.toml:15-36`; `db.py:4-6`; `.gitignore:69,104` |
| B4 | **Mounting is invasive.** It creates tables at startup across the whole shared metadata. It mounts `/static` and `/uploads` at the host root, the latter publicly. It adds the i18n and session middleware app-wide, and the session cookie is not scoped to the admin. | `core/app.py:108-116,340-374` |
| B5 | **No CSRF protection.** | 21 unsafe-method sites in templates send no token |
| B6 | **`list_view` swallows every exception.** Any failure is shown as "0 items". | `views/dynamic.py:301-313` |
| B7 | **Filters are equality-only and untyped**, and can be applied to any column. | `views/dynamic.py:250-263` |
| B8 | **sqlmodel ≥ 0.0.45 requires tz-aware datetimes** (`UTCDateTime`). The built-in auth models use `default_factory=datetime.now`, `datetime-local` inputs post naive values, and auto-now detection only recognises `datetime.now` itself. As a workaround the dependency is currently capped at `<0.0.45`. | `auth/models.py:26,59,89`; `views/forms.py:384-395`; `pyproject.toml:25` |
| B9 | **Pydantic validation messages are not translated** (#531). | `views/forms.py:494,716`; `views/dynamic.py:1545` |

The adoption thesis for this milestone: **HyperAdmin can be added to an existing FastAPI app in about 10 minutes, with fewer than 20 lines of code, without taking over the app.**

## Goals

1. **Your keys:** int, UUID and natural `str` primary keys work end to end. That covers:
   - routes and adapters;
   - views and templates;
   - inline edit, bulk actions and popups;
   - choices, inlines and object permissions;
   - realtime identity.

   A malformed key in a URL returns **404, never 500**.
2. **Your datetimes:** the admin works on sqlmodel `<0.0.45` (naive `DateTime`) and `≥0.0.45` (`UTCDateTime`). Aware values are shown in a configurable timezone (`HYPERADMIN_TIMEZONE`). The `<0.0.45` cap is removed.
3. **Your auth:** one constructor argument, `Admin(auth=ExternalAuth(get_user=<host dependency>, …))`, reuses the host's own FastAPI dependency and user model. In that mode the admin needs no `hyperadmin_*` tables, no login page and no global `SessionMiddleware`.
4. **Your app:** `Admin(app, session_factory=…).mount("/admin")` changes nothing outside `/admin`:
   - no mounts at the root;
   - no global middleware;
   - no DDL unless explicitly requested;
   - no cookie named `session`;
   - no clashes with host route names;
   - no entries in the host's OpenAPI schema.

   It works with the host's `lifespan=` and with Alembic.
5. **Your engine:** the admin accepts the host's `AsyncEngine` or its `async_sessionmaker`.
6. **Hardening:**
   - CSRF protection on every unsafe admin request, in every auth mode;
   - `list_view` logs database errors and shows them;
   - filters are typed, support ranges and only accept whitelisted fields;
   - validation messages are translated (#531).
7. **Packaging:** `pip install hyper-admin==0.5.0a1` installs a correct set of dependencies from a committed lock file, and the publish workflow smoke-tests the built wheel.
8. **Zero regression for existing int-`id` users.** URLs, route names in router mode, `url_for(..., item_id=…)` calls, `data-testid` tokens, action-handler signatures and popup JSON all stay the same.

## Non-Goals

- **An adapter for plain SQLAlchemy 2.0 `DeclarativeBase` models.** First-class support is deferred. The existing `adapters/sqlalchemy.py` only receives the primary-key fixes, so it does not fall further behind. This supersedes the `DeclarativeBase` half of the re-cut stub `st-v058-byoa-04`.
- **Composite primary keys** beyond the trivial handling: such models are registered for list and choices only, with a logged warning.
- **Changing (renaming) a natural primary key** through the admin. Keys are immutable after create.
- **String primary keys containing `/`.** They return 404 because Starlette matches on the decoded path. This is documented.
- **OAuth SSO itself** (v0.5.2, `docs/specs/oauth-sso.md`). This SDD only makes it compose: combining `oauth_backend` with `auth=` is rejected.
- **Moving built-in auth off `AuthenticationMiddleware`.** The MFA partial-auth gate stays in middleware; the two paths converge later.
- **Syncing host role or group claims** into hyperadmin permissions.
- **Per-user timezone storage.** Only a per-request override hook is provided.
- **Multiple `Admin` instances with separate registries.** `site` stays a global singleton.
- **The legacy `views/static.py` `ModelView`**, still imported by `core/model.py:75`. It stays int-only.
- **The v0.5.6 filter library UI** (`docs/specs/filter-library.md`). This SDD delivers the typed `FilterCondition` pipeline that it will compile down to.

---

## Design

### Overview: five pillars

| Pillar | What changes | Blockers closed |
|---|---|---|
| **A. Keys & datetimes** | `PrimaryKeyInfo` codec found through mapper introspection; pk-aware routes, adapters, views and templates; `core/timezones.py`; `UTCNaiveDateTime` for the auth models; the sqlmodel cap is removed | B1, B8 |
| **B. Auth bridge** | `ExternalAuth` resolved as a route-level `Depends`; a custom `APIRoute` class; the built-in auth models become opt-in; lazy `auth` imports | B2 |
| **C. Non-invasive mount** | Isolated sub-app; public lifecycle API; opt-in DDL; `session_factory`; lazy default engine; session cookie scoped to the admin; uploads served behind auth | B3 (db), B4 |
| **D. Hardening** | Signed double-submit CSRF; surfacing `list_view` errors; typed, whitelisted filters; gettext for validation messages | B5, B6, B7, B9 |
| **E. Packaging & release** | Dependency audit; committed `uv.lock`; version `0.5.0a1`; working release and publish workflows | B3 |

### Architecture

#### Module map

| Module | Status | Layer | Responsibility |
|---|---|---|---|
| `core/primary_key.py` | new | domain (pure) | `PrimaryKeyInfo`, `InvalidPrimaryKey`, `DEFAULT_PK`. Uses pydantic `TypeAdapter`; no ORM |
| `core/timezones.py` | new | domain (pure) | `utc_now`, `is_auto_now_factory`, `parse_datetime_input`, `format_datetime_input`, `to_display`. `zoneinfo` only |
| `core/filtering.py` | new | domain (pure) | `FilterCondition`, `coerce_filter_value`, `parse_filter_params`, `normalize_filters`, `FilterValueError` |
| `core/csrf.py` | new | domain (pure) | `CsrfTokenSigner` (stdlib `hmac`, `secrets` and `base64`) |
| `core/auth.py` | changed | domain | Adds `AdminAuthenticationRequired` and `AdminAccessDenied` |
| `core/adapters.py` | changed | domain | `BaseAdapter.pk`, `BaseAdapter.datetime_kind()`, `session_factory` keyword, `_session()`, `SessionFactory` typing alias |
| `core/settings.py` | changed | domain | New settings (see Configuration Changes) |
| `core/lifecycle.py` | new | logic | `AdminLifecycle`: idempotent startup/shutdown, first-request guard, table-creation scopes |
| `adapters/introspection.py` | new | adapters | `introspect_primary_key`, `datetime_kind`, `coerce_column_value`. Uses SQLAlchemy `inspect` |
| `adapters/_filter_clause.py` | new (private to `adapters/`) | adapters | `build_clause(model, FilterCondition)` |
| `adapters/sqlmodel.py`, `adapters/sqlalchemy.py` | changed | adapters | pk codec, `_session()`, `FilterCondition` lists, pk-stripping `update()` |
| `auth/bridge.py` | new | auth | `ExternalAuth`, `TokenCookie`, `CallablePermissionChecker`, `build_admin_dependency`. **Must not import `auth/models.py`** |
| `auth/_types.py` | new (private to `auth/`) | auth | `UTCNaiveDateTime` TypeDecorator |
| `auth/session_middleware.py` | new | auth | `AdminSessionMiddleware`, which preserves the host's `scope["session"]` |
| `auth/__init__.py` | changed | auth | PEP 562 lazy exports; `metadata()` |
| `views/route.py` | new | views | `make_admin_route_class()` returns `HyperAdminRoute`, which translates auth errors, bridges the token cookie and hooks in CSRF |
| `views/csrf.py` | new | views | `CsrfGuard` (reads the cookie, header or form field; checks the origin) |
| `views/urls.py` | new | views | `admin_url_for`, `install_namespaced_url_for` |
| `views/template_filters.py` | new | views | `ha_pk`, `ha_dom_token`, `ha_datetime_input`, `ha_display`, `resolve_tz` |
| `views/uploads.py` | new | views | Authenticated upload streaming with a header policy |
| `views/dynamic.py`, `views/forms.py` | changed | views | pk-agnostic handlers, tz-aware forms, typed filters, error surfacing |
| `i18n/validation_messages.py` | new | i18n | `translate_error(ErrorDetails)` |
| `routing.py` | changed | views | Per-model pk converter, literal routes registered first, `route_class` |
| `core/app.py` | changed | composition root | Wiring only (see the boundary note below) |
| `db.py` | changed | root | Lazy `get_default_engine`; deprecated module attribute `engine` |
| `management/commands/initdb.py` | new | CLI | `hyperadmin init-db` |

The table uses the names `adapters/introspection.py` and `views/template_filters.py`, not the underscore names the investigations proposed. CONSTITUTION §1 forbids importing `_private` files across modules, and both of these are consumed outside their own package.

#### Dependency flow

```
                    host app  (FastAPI, lifespan, own auth dependency, own models)
                        │  app.mount("/admin", sub_app)       Depends(get_user)
                        ▼                                         ▲
 core/app.py  Admin ── composition root: builds sub_app, routers, middleware, lifecycle
   │  (lazy imports only, as today at core/app.py:156,173,344)
   ├──► views/  route.py ─► csrf.py ─► core/csrf.py
   │           urls.py, template_filters.py ─► core/primary_key.py, core/timezones.py
   │           dynamic.py, forms.py ─► core/* contracts; BaseAdapter.pk / .datetime_kind()
   ├──► auth/   bridge.py ─► core/auth.py (exceptions, PermissionChecker)   [never auth/models.py]
   │           session_middleware.py, _types.py ─► core/timezones.py
   └──► adapters/ sqlmodel.py, sqlalchemy.py ─► introspection.py ─► core/primary_key.py, core/timezones.py
                                              ─► _filter_clause.py ─► core/filtering.py
 core/primary_key.py, core/timezones.py, core/filtering.py, core/csrf.py: pure, no ORM, no HTTP
```

**Boundary rules for this milestone**

- The new `core/*` modules import only the stdlib, pydantic and `zoneinfo`. They do not import `sqlalchemy`, `sqlmodel`, `fastapi` or `starlette`.
- Views learn primary-key and datetime facts **through the adapter contract**: `adapter.pk` and `adapter.datetime_kind(field)`. They do not import `adapters/introspection.py` directly.
  - `InlineFormset` gets the inline model's adapter from `adapter_registry`.
- `core/app.py` is the existing composition root. It keeps importing `views/`, `auth/` and `realtime/` **lazily inside methods**, as it does today. No new top-level `core → views` or `core → adapters` imports are added.
- `auth/bridge.py` may import only `core/`. A unit test running in a subprocess checks that importing it leaves `SQLModel.metadata` without any `hyperadmin_*` tables.

### A. Keys and datetimes

#### A.1 `PrimaryKeyInfo` (in `core/primary_key.py`)

```python
PkKind = Literal["int", "uuid", "str", "other"]

class InvalidPrimaryKey(ValueError): ...

@dataclass(frozen=True, slots=True)
class PrimaryKeyInfo:
    attr: str                      # mapped attribute key (not column name)
    python_type: type              # int | uuid.UUID | str | other
    generated: bool                # autoincrement / default / default_factory / server_default
    composite: bool = False
    attrs: tuple[str, ...] = ()    # all pk attrs (len > 1 only when composite)

    @property
    def kind(self) -> PkKind: ...
    @property
    def path_convertor(self) -> str: ...   # "int" | "uuid" | "hyperadmin_pk"
    def parse(self, raw: Any) -> Any: ...   # cached TypeAdapter, lax; "" rejected; raises InvalidPrimaryKey
    def to_str(self, value: Any) -> str: ...        # canonical (UUID: lowercase, hyphenated)
    def to_json(self, value: Any) -> int | str: ... # int stays int (popup back-compat)
    def value_of(self, obj: Any) -> Any: ...        # Mapping: obj.get("_pk", obj.get(attr)); else getattr

DEFAULT_PK = PrimaryKeyInfo(attr="id", python_type=int, generated=True)
```

`BaseAdapter` gains two members that are **not abstract**:
- the attribute `pk: PrimaryKeyInfo = DEFAULT_PK`;
- the method `datetime_kind(field: str) -> DateTimeKind | None`, which returns `"naive"` for datetime fields.

Third-party adapters keep working without changes.

#### A.2 Introspection (in `adapters/introspection.py`)

**`introspect_primary_key(model)`**
- Reads `sa_inspect(model).primary_key` and maps each column to its attribute key with `mapper.get_property_by_column(col).key`. This handles `sa_column=Column("id", …)` mapped under a different attribute name.
- Chooses the Python type from the first source that gives one:
  1. the pydantic annotation (with `Optional` unwrapped);
  2. `col.type.python_type`, guarding against `NotImplementedError`;
  3. `str`.
- Sets `generated` when any of these holds:
  - `autoincrement is True`;
  - `autoincrement == "auto"` on a single-column int key;
  - a `default` or `server_default` is set;
  - the pydantic field has a `default_factory` or a non-`None` default.
- Sets `composite` when the key has more than one column.

**`datetime_kind(model, field)`** returns `"aware"` or `"naive"`. The first matching rule wins:
1. The annotation is `AwareDatetime` (aware) or `NaiveDatetime` (naive).
2. The column type has `hyperadmin_tz_aware = True` (aware).
3. The column type is sqlmodel's `UTCDateTime`, when that type can be imported (aware).
4. The column type is `DateTime(timezone=True)`, or a `TypeDecorator` whose `impl.timezone` is true (aware).
5. Otherwise naive.

**`coerce_column_value(model, attr, raw)`** converts raw strings used in cascading choice filters to the column's Python type. It delegates to `core.filtering.coerce_filter_value`, so both paths coerce values the same way.

`SQLModelAdapter` and `SQLAlchemyAdapter` set `self.pk = introspect_primary_key(model)` and implement `datetime_kind`.

#### A.3 Adapter behaviour

- **`get()` and `get_related()`** filter on `getattr(model, pk.attr) == pk.parse(pk_value)`. If parsing raises `InvalidPrimaryKey`, they return `None` or `[]`, and the view turns that into a 404.
- **`update()`** drops every `pk.attrs` key from `data` before calling `setattr`. Primary keys are therefore immutable. This also fixes a bug where inline rows rewrote a UUID key with a fresh `uuid4` taken from `model_dump()`.
- **`delete()` and `update()`** parse the key before calling `session.get`.
- **`get_choices()`**:
  - the option value is `target_pk.to_str(target_pk.value_of(item))`, where `target_pk` is cached per target class;
  - cascade filter values go through `coerce_column_value`.
- **`save_inline_rows()`** checks `row.get("_pk") is not None` rather than truthiness, so a row with key `0` is not skipped.
- **Composite keys:** `get`, `get_related`, `update` and `delete` raise `NotImplementedError`.

#### A.4 Core helpers

| Helper | Change |
|---|---|
| `core/display.py` `get_display_name(instance, *, pk_attr="id")` | Falls back to the named primary-key attribute |
| `core/discovery.py:89` | Foreign-key choice values use the target adapter's `pk.to_str` |
| `core/introspection.py:153,162` | Fallback list is `[<field with FieldMeta.is_pk>, "__str__"]` |
| `core/inlines.py` `get_display_fields(pk_attr="id")` | Excludes the named primary-key attribute |

#### A.5 Routing (in `routing.py`)

1. On import, register a URL converter named `hyperadmin_pk`, only if it is not already registered.
   - Its regex is `[^/]+`.
   - `convert` returns the value unchanged.
   - `to_string` percent-encodes with `quote(str(v), safe="-._~!$&'()*+,;=:@")` and rejects `""` and any value containing `/`.
   - Starlette's `str` converter does no quoting, which is why a custom converter is needed.
2. Each model's item segment is `{item_id:<pk.path_convertor>}`:
   - **int keys** keep `{item_id:int}` byte-for-byte;
   - **UUID keys** use Starlette's `uuid` converter, so a malformed UUID never matches the route and returns 404 before any view runs.
3. **Every fixed-literal route is registered before the `/{item_id}` routes.** These are create, create-popup, choices, inline add-row, bulk, bulk-confirm and upload. Starlette uses the first full match, so for `str` keys these words become reserved segments on GET. This is documented.
4. **Composite keys** get only the list and choices routes, and log `WARNING … composite primary key; registering list-only`.
5. The `item_id` parameter name does not change.
6. The router takes `route_class=` (see pillar B).

#### A.6 `DynamicModelView` and forms

**Handlers**
- The view sets `self.pk = adapter.pk`.
- The literal `"id"` at `views/dynamic.py:111,268,1178` becomes `self.pk.attr`.
- Every item handler takes `item_id: Any`, and its first line is `pk = self._resolve_pk(item_id)`. `_resolve_pk` turns `InvalidPrimaryKey` into `HTTPException(404)`.
- The handlers covered are detail, update-form, update, delete, inline-edit-form, inline-save, delete-file and run-action.

**List rows**
- Each row sets `row["_pk"] = pk.value_of(item)`.
- `row["id"]` is still set when the model has an `id` attribute, so custom templates keep working.
- Every template context gets `pk_attr`.

**Create and update**
- Create uses `parent_pk = pk.value_of(new_item)` and compares with `is not None`.
- Before validation, update calls `data.setdefault(pk.attr, pk.value_of(existing))`, so natural keys pass validation. After validation it calls `update_data.pop(pk.attr, None)`.

**Popup, bulk and actions**
- The popup returns `"id": pk.to_json(new_pk)`. For int keys the JSON is identical to today's, and UUID keys no longer raise `TypeError` in `json.dumps`.
- `_parse_ids(form, pk)` returns `list[Any]` using `pk.parse`, and drops invalid values silently, as today.
- Action handlers receive the typed key, which is still an `int` for existing users.

**`PydanticForm`** gains three keyword-only parameters:

| Parameter | Default | Effect |
|---|---|---|
| `pk_attr` | `"id"` | Which attribute is the primary key |
| `pk_editable` | `False` | Set to `True` only on create forms where `not pk.generated`. This is what lets a natural `str` key be entered on create |
| `timezone` | `UTC` | Used to localise datetime input |

It also changes in three ways:
- `_is_auto_now_field` uses `is_auto_now_factory`.
- `_is_datetime_annotation` accepts subclasses of `datetime`, `AwareDatetime`, `NaiveDatetime` and `Annotated[datetime, …]`.
- `validate()` pre-processes datetime strings with `parse_datetime_input(kind=adapter.datetime_kind(name), tz=timezone)`.
  - A parse error becomes the field error "Enter a valid date/time", wrapped in gettext.
  - When the submitted string equals `format_datetime_input(initial[name], tz)`, the original value is kept, so microseconds survive an edit.

**`InlineFormset`**
- Gets `pk` from the inline model's adapter.
- `InlineFormRow.pk` is typed `Any`.
- `int(pk_val)` becomes `pk.parse`. If parsing fails, that row gets an error.
- `getattr(inst, "id")` becomes `pk.value_of`.

#### A.7 Timezones (in `core/timezones.py`)

```python
DateTimeKind = Literal["aware", "naive"]
def utc_now() -> datetime: ...   # aware UTC; marked __hyperadmin_auto_now__ = True
def is_auto_now_factory(fn) -> bool: ...
    # datetime.now / utcnow / utc_now, partials of those, __hyperadmin_auto_now__,
    # or a lambda/def whose __code__.co_names contains "now" or "utcnow"
def parse_datetime_input(raw: str, *, kind: DateTimeKind, tz: tzinfo) -> datetime: ...
    # aware: naive input -> replace(tzinfo=tz, fold=0) -> astimezone(UTC); offsets respected
    # naive: kept as entered; offset input -> astimezone(tz).replace(tzinfo=None)
def format_datetime_input(value, tz) -> str: ...  # aware -> astimezone(tz); isoformat(timespec="seconds")
def to_display(value: datetime, tz: tzinfo, fmt: str) -> str: ...  # only transforms aware values
```

**Settings:**
- New setting `timezone: str = "UTC"` (environment variable `HYPERADMIN_TIMEZONE`), validated with `ZoneInfo(value)`.
- The existing `datetime_format` setting (`core/settings.py:91-92`), unused until now, finally drives `to_display`.

**Per-request override:** a host middleware, or the auth bridge, may set `request.state.hyperadmin_timezone`. There is no `Admin()` parameter for this: under the settings rule, scalar configuration lives in settings.

**New runtime dependency:** `tzdata; sys_platform == 'win32'`. `zoneinfo` needs it on Windows (CONSTITUTION §6).

#### A.8 Built-in auth timestamps

`auth/_types.py` defines this column type:

```python
class UTCNaiveDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=False); cache_ok = True; hyperadmin_tz_aware = True
    # bind: aware -> astimezone(UTC).replace(tzinfo=None); naive -> assumed UTC
    # result: naive -> replace(tzinfo=UTC)
```

In `auth/models.py:26,59,89`, the timestamp fields become `created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime())`. The `sa_type=` argument exists since sqlmodel 0.0.14, so this works with the 0.0.19 floor.

This column type:
- keeps the existing `timestamp without time zone` DDL, so **no migration** is needed;
- avoids asyncpg's rejection of aware values bound to `timestamp` columns;
- hands Python code aware UTC values on both sides of the sqlmodel cap.

#### A.9 Template filters (in `views/template_filters.py`)

| Filter | Behaviour |
|---|---|
| `ha_pk(item, pk_attr="id")` | Returns the key using `value_of` semantics, for both row dicts and model instances. Used in `url_for` calls |
| `ha_dom_token(value)` | Returns `str(value)` if it matches `[A-Za-z0-9_.:-]+`. Otherwise returns `"h" + blake2b(str(value), digest_size=6).hexdigest()`. Used in DOM ids and `data-testid` values. **Tokens for int and UUID keys are unchanged** |
| `ha_datetime_input(value)` | Takes the template context. Returns `format_datetime_input(value, resolve_tz(ctx))` |
| `ha_display(value)` | For aware datetimes, renders `<time datetime="{utc iso}">{local text}</time>`. Every other value passes through unchanged |

**Templates:**
- `item.id` becomes `item|ha_pk(pk_attr)` in URLs and `…|ha_dom_token` in ids and testids. This applies to `components/table.html`, `components/inline_cell.html`, `components/inline_editor.html`, `components/inline_cell_error.html`, `update.html` and `detail.html`.
- In `components/table.html:16`, `field != 'id'` becomes `field != pk_attr`.
- Display cells use `|ha_display`.
- In `widgets/datetime_input.html`, the input uses `|ha_datetime_input` and `step="1"`. It also shows a timezone hint with `data-testid="{field}-tz"`.

#### A.10 Removing the sqlmodel cap

This is the last story of pillar A.
- `pyproject.toml` changes to `sqlmodel>=0.0.19`.
- `examples/simple/models.py:31,41` and the test fixtures in `tests/unit/test_introspection.py:37` and `tests/unit/test_zero_config.py:45` switch to `utc_now`.
- Run `poe deps:bump`, which verifies three combinations: Python 3.10 with lowest-direct dependencies (sqlmodel 0.0.19), Python 3.13 with lowest-direct, and Python 3.13 with highest (sqlmodel ≥ 0.0.47).
- The timezone unit tests use explicit column types. The `UTCDateTime` tests are skipped when that type is not importable, so the suite is meaningful on both sides of the cap.
- Refresh the visual baselines that show datetimes. **Never bypass them with `--no-verify`.**

### B. Auth bridge ("bring your own auth")

#### B.1 Why a route-level `Depends` instead of middleware

The bridge is attached as `include_router(protected_router, dependencies=[Depends(admin_user)])`. This lets FastAPI resolve the host dependency natively, including:
- sub-dependencies (`OAuth2PasswordBearer`, `get_db`);
- `Security` scopes;
- dependencies that `yield`;
- sync functions;
- `app.dependency_overrides` in the host's tests.

A middleware would need FastAPI's private `solve_dependencies` API. The route-level dependency also scopes auth to admin routes only.

#### B.2 Why a custom `APIRoute` class

A host dependency using `OAuth2PasswordBearer(auto_error=True)` raises `HTTPException(401)` before our code runs. The only admin-scoped place to turn that into a browser redirect is a wrapper around the route handler.

`make_admin_route_class(...)` returns `HyperAdminRoute`, which is set as `route_class` on every admin `APIRouter` (`routing.py:61,284` and the routers in `core/app.py`). FastAPI's `include_router` keeps `type(route)`. This one class is also the only place that:
1. copies the token cookie into an `Authorization` header;
2. verifies CSRF;
3. attaches the CSRF cookie to the response;
4. maps auth errors to responses:

| Condition | Plain browser request | HTMX request (`HX-Request`) | API prefix (`/realtime/`) |
|---|---|---|---|
| `AdminAuthenticationRequired` or host 401, with `login_url` set | 303 to `login_url?next=<admin path+query>` | 401 plus `HX-Redirect: <same>` | 401 |
| The same, without `login_url` | 401 HTML page: "Sign in to the host application" | 401 plus `HX-Refresh: true` | 401 |
| `AdminAccessDenied` or host 403 | 403 HTML page naming `can_access` | 403 | 403 |
| Any other error | Passed through unchanged | | |

The `next` value is always the relative admin path built on the server, never user input, so it cannot be used as an open redirect.

In built-in mode, the same route class still does CSRF, but auth redirects stay in `AuthenticationMiddleware`.

#### B.3 Wiring in `Admin`

This applies when `auth=ExternalAuth(...)` is set.

**Validation**
- Passing `auth` together with `auth_backend`, `otp_service` or (in future) `oauth_backend` raises `ValueError`, naming both parameters.

**Routers**
- There are two routers. `router` (protected) is included with `Depends(build_admin_dependency(auth))`.
- `public_router` holds only the token-handoff route.
- There is no login route, no MFA routes and no `SessionMiddleware` or `AuthenticationMiddleware`.
- `POST {prefix}/logout` is protected and CSRF-checked. It clears the token cookie, then returns 303 to `logout_url or "/"`.

**Permission checker**, first match wins:
1. an explicit `Admin(permission_checker=…)`;
2. `auth.has_permission`, wrapped in `CallablePermissionChecker` when it is a plain callable;
3. `None`: full access for every user who passes `can_access`, plus a startup `WARNING` (see Owner decision 3).

**Other wiring**
- `core/app.py:161` changes its guard from `if self.auth_backend` to `if self._auth_mode is not None`.
- **The built-in auth models are opt-in.** `settings.register_auth_models: bool | None = None`, where `None` means "on for `auth_backend`, off for `auth=`". This controls `_register_auth_models`. `_sync_permissions` runs only when `permission_registry` is set.
- Template globals: `auth_enabled=True`, `auth_mode="external"`, `logout_url`.
- `request.state` keys shared by both modes: `user`, `user_key` and `user_display`. `AuthenticationMiddleware` sets them too.

#### B.4 Token handoff for bearer-only apps

This is enabled only when `token_cookie=TokenCookie()` is set. Apps that already authenticate with a cookie need none of it.

**`POST {prefix}/auth/session`**
- It lives on the public router and is exempt from CSRF: it is authenticated by the `Authorization` header, which a cross-site page cannot set.
- It validates the bearer token by calling the host dependency through an internal sub-application request.
- On success it sets `hyperadmin_token=<jwt>` with `HttpOnly`, `SameSite=Lax`, `Path=<prefix>`, `Max-Age`, and `Secure` when served over https. It then returns 204, or 303 to a validated `next`.
- It returns 400 if the token is longer than 3,800 bytes, and 401 if the host rejects it (no cookie is set).

**On later admin requests**, the route class copies the cookie into `Authorization: <scheme> <token>`, but **only when no `Authorization` header is present**. It does this by building a new `Request` from a copied scope before dependency solving.

#### B.5 Import hygiene

`auth/__init__.py` switches to PEP 562 lazy `__getattr__`:
- `from hyperadmin.auth import User` still works.
- `from hyperadmin.auth import ExternalAuth` no longer imports `auth/models.py`, so it no longer registers `hyperadmin_*` tables.
- `hyperadmin.auth.metadata()` returns a copy of the metadata containing only the `hyperadmin_*` tables, for Alembic users.

#### B.6 Closing the authorization gaps

Story `st-v058-byoa-10` (see Owner decision 4) adds these checks:

| Handler | Model-level check | Object-level check |
|---|---|---|
| `inline_edit_form_view`, `inline_save_view` | `_check_permission("change")` | `_check_object_permission(item, "change")` |
| `update_form_view`, `delete_file_view` | already present | `"change"` |
| `run_action` | already present | Loads the object, applies `_request_queryset_filter`, then checks `f"action_{name}"`, mirroring the bulk path at `views/dynamic.py:1414` |

### C. Non-invasive mount

#### C.1 Isolated sub-application (the default)

`Admin.mount(path)` builds a private `FastAPI(openapi_url=None, docs_url=None, redoc_url=None)` and attaches it with `app.mount(path, sub_app, name=settings.route_namespace)`. As a result:

- **Middleware is scoped to the admin.** `LocaleMiddleware`, `AdminSessionMiddleware` and `AuthenticationMiddleware` wrap only admin requests.
- **Admin assets move under the prefix:** `/static`, `/uploads` and `/realtime/ws` become `{prefix}/static/…`, `{prefix}/uploads/…` and `{prefix}/realtime/ws`.
  - The `/static` mount moves **out of `Admin.__init__`**, where it happens today at `core/app.py:108-110`, into `mount()`.
- **Route names are namespaced** as `hyperadmin:user-list`, and admin routes are left out of the host's OpenAPI schema.
- **Legacy mode.** `settings.mount_mode = "router"` keeps today's exact behaviour: `include_router`, global middleware, `/static` at the root and un-namespaced route names. It emits a `DeprecationWarning` and is removed in 0.6.
- **Mounting at the root.** `mount("/")` forces router mode and logs why: a Mount at the root would shadow every host route.
- **The auth bridge in isolated mode.** The protected and public routers are included into the sub-app. The auth dependency and route class behave exactly as in B.3.

**Resolving URLs.** `views/urls.py` provides:
- `admin_url_for(request, name, **params)`: it tries `f"{ns}:{name}"` when `request.app.state.hyperadmin_namespace` is set, and plain `name` otherwise.
- `install_namespaced_url_for(env)`: it replaces the Jinja `url_for` global with a context-aware wrapper that falls back the same way.

With these, none of the roughly 25 template `url_for` calls needs editing, and host-overridden templates that link to host routes keep working. The 9 `request.url_for` calls in `views/dynamic.py` switch to `admin_url_for`.

**Admin prefix check in `AuthenticationMiddleware`:**
- In the sub-app it uses `get_route_path(scope)`.
- In router mode it requires a segment boundary: `path == prefix or path.startswith(prefix + "/")`. This fixes `/administrator` being treated as an admin path (`auth/middleware.py:45`).

#### C.2 Lifecycle

- Every `app.on_event` and `router.on_startup` use is removed (`core/app.py:112-116,290-292,477`).
- New public, idempotent methods:
  - `await admin.startup()` creates tables (if opted in), then syncs permissions;
  - `await admin.shutdown()` drains realtime connections;
  - `admin.lifespan()` is an async context manager the host can compose into its own lifespan.
- **Safety net.** Starlette silently ignores `on_event` handlers when the host passes `lifespan=`. So a sub-app `_StartupGuard` runs `startup()` exactly once, under an `asyncio.Lock`, on the first admin request. Failures are logged and not cached, so the next request retries. When the host keeps Starlette's default lifespan, `mount()` also appends to `app.router.on_startup` and `on_shutdown`.
- **`create_tables` defaults to `False`.**
  - `await admin.create_tables(scope="hyperadmin" | "all")`. Setting `settings.create_tables=True` keeps today's `"all"` behaviour.
  - **Demo mode:** when neither `engine` nor `session_factory` is passed, a lazy default engine is built from `settings.database_url` and tables are created automatically, with `WARNING "HyperAdmin demo mode"`. Zero-config `Admin(app).mount("/admin")` keeps working.
  - New CLI command: `hyperadmin init-db --database-url URL [--all]`.
- The private `_create_db_and_tables()` and `_sync_permissions()` remain as aliases for one release. The ERP example uses them.

#### C.3 Engine or session factory

**`db.py`**
- Creates no engine when imported.
- `get_default_engine(settings)` builds one lazily and caches it per URL.
- A module-level `__getattr__("engine")` keeps `from hyperadmin.db import engine` working, with a `DeprecationWarning`.

**`core/adapters.py`**
- Adds the typing alias `SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSessionLike]]`. It is typing only, so `core/` stays free of ORM code.
- `BaseAdapter.__init__(model, engine=None, *, session_factory=None)` raises `ValueError` when both are `None`.
- `BaseAdapter._session()` opens a session from whichever was given.

**Call sites**
- All 20 `AsyncSession(self.engine)` sites move to `self._session()`.
- `SessionAuthBackend`, `ModelPermissionChecker` and `PermissionSyncService` gain the same `session_factory` keyword.
- An `async_sessionmaker` works as-is. A host that uses a generator dependency passes `asynccontextmanager(get_session)`.
- Creating tables needs an engine. It is taken from `session_factory.kw["bind"]` when available; otherwise `create_tables` raises an error explaining what to pass.

#### C.4 Session cookie scoped to the admin

New settings:

| Setting | Default |
|---|---|
| `session_cookie` | `"hyperadmin_session"` |
| `session_max_age` | `1209600` |
| `session_same_site` | `"lax"` |
| `session_https_only` | `None`, which means `not debug` |

The cookie `path` is the admin prefix.

In isolated mode, `AdminSessionMiddleware` wraps Starlette's `SessionMiddleware`. It saves the host's `scope["session"]` and restores it before forwarding `http.response.start`. A `Mount` shares the scope dict, so without this the host's session middleware would serialise the admin session into the host cookie.

In router mode, the legacy cookie settings (`session`, path `/`) stay the default unless set explicitly.

#### C.5 Uploads behind auth

The public mount at the root (`core/app.py:363-374`) is removed. `views/uploads.py` serves `GET {prefix}/uploads/{path:path}` (route name `uploads`), streaming from `storage`. It:
- returns 404 for path traversal;
- sends `X-Content-Type-Options: nosniff` and `Content-Security-Policy: sandbox`;
- sends `Content-Disposition: attachment` for everything except PNG, JPEG, GIF and WebP (**not SVG**).

`detail.html:14` changes to `url_for('uploads', path=value)`.

Escape hatch: setting `settings.public_uploads_path` restores the legacy public mount, with a startup warning.

### D. Hardening

#### D.1 CSRF: signed double-submit cookie (all auth modes)

**`core/csrf.py` `CsrfTokenSigner`**
- `issue()` returns `"<nonce_b64url>.<hmac_b64url>"`.
- `is_valid()` checks the signature in constant time.
- `matches(cookie, submitted)` compares with `hmac.compare_digest`.

**Token lifecycle.** On every admin request, `views/csrf.py` `CsrfGuard.ensure_token`:
- reads `hyperadmin_csrf`;
- if the cookie is missing or its signature is invalid, issues a new cookie (`HttpOnly; SameSite=Lax; Path=<prefix>`, plus `Secure` over https);
- sets `request.state.csrf_token`.

Tokens are per cookie, not per request, so several tabs and parallel HTMX requests stay valid.

**Unsafe methods** are checked in this order:
1. `Sec-Fetch-Site: cross-site` fails.
2. An `Origin` that is neither same-origin nor listed in `csrf_trusted_origins` fails.
3. The token is taken from the `X-CSRF-Token` header. If there is none, it is taken from the `csrf_token` form field of a urlencoded or multipart body, using Starlette's cached `request.form()`.
4. The token must pass `is_valid` and `matches(cookie)`.

**On failure** the response is 403 "CSRF token missing or invalid" with `X-HyperAdmin-CSRF: failed`. In `report` mode the request goes through and a `WARNING` is logged.

**Modes.** `csrf_mode` is one of `"auto" | "enforce" | "report" | "off"`, where `auto` means enforce whenever any auth is configured, and off otherwise. Apps with no auth see no change.

**Exempt:** the token-handoff path. WebSockets do not go through `APIRoute`, so the WebSocket handler checks `Origin` itself, which closes cross-site WebSocket hijacking.

**UI:**
- `_base.html` sets `<body hx-headers='{"X-CSRF-Token": "{{ csrf_token() }}"}'>`, which every htmx request inherits.
- A `<meta name="csrf-token">` tag serves JS `fetch` calls.
- The `csrf_input()` Jinja global is added to every plain `<form method="post">`: `_navbar.html`, `login.html`, `auth/mfa_*.html`, `components/bulk_form.html`, `components/bulk_result.html` and `widgets/popup_form.html`.
- A 403 carrying `X-HyperAdmin-CSRF` shows a "reload page" banner.

**Login.** `GET /login` issues the cookie, and `POST /login` is verified, which blocks login CSRF.

**Secret key.** `_validate_session_secret` (`core/app.py:130`) becomes `_validate_secret_key` and also fires when `auth=` is set or CSRF resolves to enforce.

#### D.2 `list_view` shows errors instead of swallowing them

`views/dynamic.py:301-313` catches only `SQLAlchemyError`. When it does, it:
1. calls `logger.exception`;
2. re-raises if `settings.debug` is true;
3. otherwise renders a `list-error` banner (`data-testid="list-error"`), with status 500 for a full page or 200 for an HTMX partial.

When the error is an `OperationalError` matching `no such table|does not exist|UndefinedTable`, the banner adds the hint "run your migrations or `hyperadmin init-db`". Exceptions that are not database errors propagate.

#### D.3 Typed, whitelisted filters (in `core/filtering.py`)

```python
FilterOp = Literal["exact", "gte", "lte", "in", "isnull"]
@dataclass(frozen=True)
class FilterCondition: field: str; op: FilterOp; value: Any
class FilterValueError(ValueError): ...
def coerce_filter_value(annotation: Any, raw: str) -> Any: ...   # bool/int/float/Decimal/UUID/Enum/date/datetime/str
def parse_filter_params(model, params, allowed) -> ParsedFilters: ...  # conditions, active, errors
def normalize_filters(filters: Mapping | Sequence[FilterCondition] | None) -> list[FilterCondition]: ...
```

**Query syntax**
- `filter_<f>=v` is an exact match, as today.
- The operators are `__gte`, `__lte`, `__in=a,b` (the parameter may also repeat) and `__isnull=true`.
- An exact `date` value on a `datetime` column becomes the range `[d, d+1)`.
- On aware columns, date bounds are converted with `core/timezones.py` using the display timezone.

**Rules**
- Only fields named in `options.list_filter` are allowed. Anything else is ignored and logged at `DEBUG` (Owner decision 7).
- A value that cannot be coerced drops that condition. The page still returns 200, with an inline `filter-error`.

**Adapters.** `adapters/_filter_clause.build_clause` is shared by both adapters. `BaseAdapter.list(filters=...)` accepts either the legacy dict or a `Sequence[FilterCondition]`.

`core/discovery.build_filter_metadata` gains range kinds (date, datetime and number), so the filter bar can render range inputs. The v0.5.6 filter-library `FilterDef` later compiles down to `FilterCondition`.

#### D.4 Validation messages through gettext (#531)

`i18n/validation_messages.translate_error(err)` maps pydantic's `err["type"]` to a gettext msgid with `%(ctx)s` placeholders. It covers about 25 error types, including:
- `missing`;
- string length (`string_too_short`, `string_too_long`) and `string_pattern_mismatch`;
- numeric bounds (`greater_than…`, `less_than…`) and `multiple_of`;
- the parsing errors (`…_parsing`);
- `enum` and `literal_error`;
- collection length (`too_short`, `too_long`);
- `url_parsing` and `json_invalid`.

`value_error` passes its message through gettext. Unknown types fall back to `gettext(err["msg"])`.

The msgids are marked with `gettext_noop` so that `poe i18n:extract` finds them.

It replaces the three current call sites: `views/forms.py:494` and `views/forms.py:716`, which wrap an already-interpolated string, and `views/dynamic.py:1545`, which does not translate at all.

### E. Packaging and release

**Dependencies (`[project.dependencies]`)**
- Add `pydantic-settings` (lower bound: Open Question 1).
- Change `fastapi[standard]>=0.116.0` to `fastapi>=0.116.0`.
- Drop `appnope`, `uvicorn` and `httpx` (they move to dev dependencies).
- Remove the duplicate `python-multipart` entry, keeping `>=0.0.26`.
- Add `tzdata; sys_platform == 'win32'`.
- Add a one-line comment for each dependency that is not obvious.
- Remove the GHSA-4xgf-cpjx-pc3j ignore once the lower bound includes the fix. The comment on that ignore currently claims pydantic-settings is dev-only, which is wrong.

**Lock file**
- Commit `uv.lock`: delete `.gitignore:69` and add `!uv.lock` after `.gitignore:104`.
- CI runs `uv sync --locked --all-extras`.
- `ci.yml` also runs on `pull_request` targeting `[master, develop]`.

**Version**
- The version becomes `0.5.0a1` (PEP 440).
- Commitizen gets `version_scheme = "pep440"` and `major_version_zero = true`.
- `hyperadmin.__version__` comes from `importlib.metadata`.
- The package version is decoupled from the roadmap labels (`v0.5.x`).

**`publish.yml`**
- Triggers on `release: published`, not `created`, which also fires for drafts.
- The `build` job runs `uv build` and `twine check`, then installs the wheel into a clean venv and runs `from hyperadmin import Admin`. That smoke test catches missing runtime dependencies such as pydantic-settings.
- The `publish` job (`environment: pypi`) publishes with trusted publishing via `uv publish`.

**`release.yml`**
- Pushes to `master`; today it targets the non-existent `main`.
- Runs `gh release create v$VER --generate-notes`, adding `--prerelease` for `a`, `b` and `rc` versions.

**Docs.** The README and getting-started guide say `pip install hyper-admin==0.5.0a1`, noting that the import name is `hyperadmin`.

### Data Model Changes

- **`hyperadmin_users`, `hyperadmin_groups`, `hyperadmin_permissions`:** the `created_at` columns keep their DDL, a naive `timestamp`. Only the Python side changes: `sa_type=UTCNaiveDateTime()` and `default_factory=utc_now`. **No migration.**
- No new tables or columns.
- In bridge mode, the `hyperadmin_*` tables are not registered at all unless `register_auth_models=True`.

### API / Protocol Changes

Every change is additive. New symbols are opt-in imports (CONSTITUTION §4).

```python
# hyperadmin.core.app
class Admin:
    def __init__(self, app, engine=None, settings=None, auth_backend=None,
                 permission_checker=None, permission_registry=None, storage=None,
                 otp_service=None, realtime=None, *,
                 session_factory: SessionFactory | None = None,   # NEW (pillar C)
                 auth: ExternalAuth | None = None) -> None: ...   # NEW (pillar B)
    def mount(self, path: str = "/admin") -> None: ...
    @property
    def asgi_app(self) -> FastAPI | None: ...           # isolated sub-app after mount()
    async def startup(self) -> None: ...                 # idempotent
    async def shutdown(self) -> None: ...
    def lifespan(self) -> AbstractAsyncContextManager[None]: ...
    async def create_tables(self, scope: Literal["hyperadmin", "all"] = "hyperadmin") -> None: ...

# hyperadmin.auth (lazy)
@dataclass(frozen=True, slots=True, kw_only=True)
class TokenCookie:
    name: str = "hyperadmin_token"; scheme: str = "Bearer"
    max_age: int | None = 8 * 3600; handoff_path: str = "/auth/session"

@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalAuth:
    get_user: Callable[..., Any]                        # any FastAPI dependency; None = anonymous
    can_access: Callable[[Any], MaybeAwaitable[bool]] = default_can_access   # is_superuser or is_staff
    has_permission: Callable[[Any, str], MaybeAwaitable[bool]] | PermissionChecker | None = None
    login_url: str | None = None
    logout_url: str | None = None
    next_param: str = "next"
    display_name: Callable[[Any], str] = default_display_name  # username -> email -> name -> str()
    user_key: Callable[[Any], Hashable] = default_user_key     # getattr(user, "id")
    token_cookie: TokenCookie | None = None
    websocket_user: Callable[[WebSocket], Awaitable[Any | None]] | None = None

class CallablePermissionChecker:   # satisfies core.auth.PermissionChecker
    def __init__(self, fn: Callable[[Any, str], MaybeAwaitable[bool]]) -> None: ...
def build_admin_dependency(auth: ExternalAuth) -> Callable[..., Awaitable[Any]]: ...
def metadata() -> MetaData: ...    # hyperadmin_* tables only (Alembic)

# hyperadmin.core
class PrimaryKeyInfo: ...; class InvalidPrimaryKey(ValueError): ...; DEFAULT_PK
class AdminAuthenticationRequired(Exception): ...; class AdminAccessDenied(Exception): ...
class FilterCondition: ...; class FilterValueError(ValueError): ...
def utc_now() -> datetime: ...
BaseAdapter.pk: PrimaryKeyInfo                          # non-abstract, default DEFAULT_PK
BaseAdapter.datetime_kind(field) -> DateTimeKind | None  # non-abstract
BaseAdapter.__init__(model, engine=None, *, session_factory=None)
BaseAdapter.list(..., filters: Mapping | Sequence[FilterCondition] | None)

# hyperadmin.db
def get_default_engine(settings: HyperAdminSettings | None = None) -> AsyncEngine: ...
# hyperadmin.views.urls
def admin_url_for(request: Request, name: str, /, **path_params: Any) -> URL: ...
# hyperadmin
__version__: str
```

**HTTP surface**
- **Item URLs** use the per-model key converter; int keys keep the same URLs.
- **New:**
  - `POST {prefix}/auth/session` (bridge mode, with `token_cookie`);
  - `POST {prefix}/logout` (bridge mode);
  - `GET {prefix}/uploads/{path}`.
- **Moved (isolated mode):** `/static` becomes `{prefix}/static`, and `/uploads` becomes `{prefix}/uploads`.
- **New response headers:** `X-HyperAdmin-CSRF`; `HX-Redirect` / `HX-Refresh` on 401 in bridge mode.
- **Popup `HX-Trigger`:** `id` is a JSON number for int keys and a string otherwise.
- **CLI:** `hyperadmin init-db --database-url URL [--all]`.

### Configuration Changes

All new configuration lives in `HyperAdminSettings`, prefix `HYPERADMIN_`. Non-scalar objects are passed as `Admin(...)` keywords: `auth=` and `session_factory=`.

| Setting | Type / default | Pillar |
|---|---|---|
| `timezone` | `str = "UTC"` (validated with `ZoneInfo`) | A |
| `register_auth_models` | `bool \| None = None`. `None` resolves to on with `auth_backend` and off with `auth=` | B |
| `csrf_mode` | `"auto" \| "enforce" \| "report" \| "off" = "auto"` | D |
| `csrf_cookie_name` / `csrf_header_name` / `csrf_field_name` | `"hyperadmin_csrf"` / `"X-CSRF-Token"` / `"csrf_token"` | D |
| `csrf_trusted_origins` | `list[str] = []` | D |
| `create_tables` | `bool = False` (**default changed**; was `True`) | C |
| `mount_mode` | `"isolated" \| "router" = "isolated"` | C |
| `route_namespace` | `str = "hyperadmin"` | C |
| `session_cookie` / `session_max_age` / `session_same_site` / `session_https_only` | `"hyperadmin_session"` / `1209600` / `"lax"` / `None` | C |
| `public_uploads_path` | `str \| None = None` | C |
| `database_url` | existing; **now actually used**, for demo mode only | C |
| `datetime_format` | existing; **now actually used** by `ha_display` | A |

### How the three investigations were reconciled

| Topic | Conflict between investigations | Resolution |
|---|---|---|
| Datetime helper module | Pillar C cited `core/datetimes.py`; pillar A defined `core/timezones.py` | **`core/timezones.py`** is the only module. The date-range filters use it |
| Value coercion | `adapters/_introspect.coerce_column_value` (A) vs `core/filtering.coerce_filter_value` (C) | `core/filtering.coerce_filter_value` is the single pure coercer. `adapters/introspection.coerce_column_value` resolves the column's type and delegates to it |
| Private-module imports | `adapters/_introspect.py` and `views/_templating.py` were meant to be imported across modules | Renamed to `adapters/introspection.py` and `views/template_filters.py`. Views reach introspection through `BaseAdapter.pk` / `.datetime_kind()` |
| Realtime user id | Both A and B widened `RealtimeConnection.user_id` | **One story** (`st-v058-byoa-42`): widen to `Hashable` and read the key from `request.state.user_key` |
| Authorization gaps | A listed them as an open question; B had a story | **One story** (`st-v058-byoa-10`), a `fix` that can ship early (Owner decision 4) |
| Session cookie vs bridge | C adds `AdminSessionMiddleware`; B says bridge mode has no session middleware | Both hold. `AdminSessionMiddleware` is installed **only** for built-in auth, and bridge mode uses the token cookie or the host's own cookie |
| CSRF cookie path and route class vs sub-app | B assumed an `APIRouter` include; C builds a sub-app | The route class goes on every admin router, and those routers are included **into the sub-app**. `Path=<prefix>` holds in both modes because `root_path` equals the prefix |
| Table creation | B's `register_auth_models` vs C's `create_tables` scope | Kept separate. `register_auth_models` decides whether the tables are *registered*; `create_tables` / `init-db` decides whether DDL runs. In bridge mode the default is no registration, so no DDL either |
| Multi-tenancy (v0.5.3) | Its SDD resolves tenants in `TenantMiddleware` from `request.state.user`. That is empty in bridge mode, where the user is only resolved during dependency solving | Amend `docs/specs/multi-tenancy.md` so tenants are resolved in a route dependency that runs after the admin principal, or in `ModelAdmin.get_queryset`. This works in both modes and is done in the docs story |
| DeclarativeBase | The re-cut stub `st-v058-byoa-04` included it | Out of scope. The host engine/session reuse half is kept (`st-v058-byoa-21`) |
| Changes to the same lines | A and C both edit `dynamic.py` (`row["id"]`, `url_for`) and `routing.py` | The stories are sequenced by `Blocked by` (see the Story breakdown). The pillar A view stories land before `st-v058-byoa-34` and `st-v058-byoa-35` |

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Malformed UUID in the URL | The `uuid` converter does not match, so 404 before any view runs |
| Malformed `str` or other key | `_resolve_pk` raises `InvalidPrimaryKey`, which becomes a 404 |
| A `str` key equal to `create`, `choices`, `upload`, … | The literal route wins on GET. Documented. `/m/create/edit` still works |
| A `str` key containing `/` | 404. Documented as a non-goal |
| A `str` key with spaces, `?`, `#` or `%` | `hyperadmin_pk.to_string` percent-encodes it, and it round-trips |
| Composite key | List and choices only, plus a warning. Item adapter methods raise `NotImplementedError` |
| Update data containing the key attribute | The adapter strips it, so keys cannot change |
| Inline row with `_pk=0` | Handled with an `is not None` check |
| DST gap or overlap in `parse_datetime_input` | `fold=0`, unit-tested with Europe/Amsterdam spring-forward |
| Unchanged datetime resubmitted with lower precision | The original value is kept, microseconds included |
| A user lambda that calls `now` is treated as auto-now | Matches today's intent. Escape hatch: a named function. Documented |
| Host dependency raises 401 itself | Treated as anonymous (see B.2) |
| Host dependency needs query or path parameters | FastAPI returns 422. Documented: the dependency must resolve from headers and cookies alone |
| Sync host dependency or `can_access` | FastAPI runs it in its threadpool; `_maybe_await` normalises the callables |
| Both an `Authorization` header and the token cookie | The header wins |
| Host user without `.id`, `.username` or `is_staff` | Override `user_key`, `display_name` or `can_access`. The default `can_access` denies with a 403 that names the setting |
| `auth=` together with `auth_backend`, `otp_service` or `oauth_backend` | `ValueError` at construction |
| Bridge mode without `websocket_user` | The WebSocket route is not registered (INFO log). SSE still works |
| Stale CSRF cookie after the secret rotates | A new cookie is issued on the next GET. An HTMX POST gets 403 plus `X-HyperAdmin-CSRF`, and a reload banner is shown |
| Multipart upload over HTMX | The token comes from the header, so the body is not parsed early |
| Admin served over plain http in dev or TestClient | `Secure` is left off |
| Startup race on the first requests | `asyncio.Lock` plus a `_started` flag. A failure is logged and retried on the next request |
| Host's own `SessionMiddleware` uses the cookie `session` | `AdminSessionMiddleware` saves and restores the host's scope. Tested |
| Host has no `lifespan` | The guard is backed by an `on_startup` fallback |
| `mount("/")` | Forced to router mode, with a warning |
| Missing table or migration | `list-error` banner with the migration hint, plus an `ERROR` log with the traceback |
| Filter on a column not in `list_filter` | Ignored (`DEBUG` log) |
| Invalid filter value | The condition is dropped, the page returns 200 and a `filter-error` is shown |
| Upload path traversal, or an SVG or HTML upload | 404 for traversal. For SVG and HTML: `attachment`, `nosniff` and `CSP: sandbox` |
| `session_factory` without a bind, with `create_tables=True` | An error explaining what to pass |

## Migration & Backward Compatibility

The package is pre-1.0 (`major_version_zero`), so breaking defaults are allowed in a minor release. Every break below has an escape hatch and an entry in the changelog and upgrade note.

| Existing user | Effect | Action |
|---|---|---|
| Int-`id` models, any mode | URLs, `url_for(..., item_id=…)`, `data-testid` tokens, action-handler `int` ids, popup JSON number and bulk id parsing are all unchanged | None |
| Custom templates using `item.id` | Still work for int-`id` models, because rows still carry `"id"` | Use `item\|ha_pk(pk_attr)` to support other key types |
| Third-party `BaseAdapter` subclasses | Inherit `pk = DEFAULT_PK`; `super().__init__(model, engine)` still works | None |
| Direct `PydanticForm` users | The defaults keep today's behaviour | None |
| Built-in auth (`auth_backend=`) | Same login, MFA and auto-registered auth admins. **CSRF is enforced.** The cookie is renamed, so users log in again once | Add `{{ csrf_input() }}` to custom raw POST forms, or temporarily set `HYPERADMIN_CSRF_MODE=report` |
| Relied on `create_tables=True` being the default | Tables are no longer created automatically, except in demo mode | Set `create_tables=True`, or use Alembic or `hyperadmin init-db` |
| Linked to `/static/…` or `/uploads/…` directly | These moved under the admin prefix | Update the links, or set `public_uploads_path` / `mount_mode="router"` |
| Host code reads a `request.session` that HyperAdmin created | HyperAdmin no longer installs session middleware globally | Add your own `SessionMiddleware`, or use `mount_mode="router"` |
| `app.url_path_for("user-list")` | The name is now `hyperadmin:user-list` | Use the namespaced name, or router mode |
| `from hyperadmin.db import engine` | Still works, with a `DeprecationWarning` | Pass your own engine or session factory |
| Private `_create_db_and_tables()` / `_sync_permissions()` | Kept as aliases for one release | Use `create_tables()` / `startup()` |
| `filter_x=` on fields not in `list_filter` | Ignored (security fix) | Add the field to `list_filter` |
| Existing `hyperadmin_*` rows on a server not running in UTC | `created_at` is read back as UTC, so it appears shifted by the server's offset | Release note only (Owner decision 6) |
| User-owned Postgres `timestamp` columns after upgrading sqlmodel | This is the user's own schema | Migrate to `timestamptz`, or annotate the field with `NaiveDatetime`. HyperAdmin handles both |
| Apps with no auth configured | `csrf_mode=auto` resolves to off | None |
| Unit tests that POST to admin routes | CSRF enforcement applies to them | Use the `csrf_client` helper added to `tests/conftest.py`, or set `csrf_mode="off"` |

## Risks

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Starlette's namespaced `url_for` does not resolve through a mounted FastAPI sub-app | Medium / High | Story `st-v058-byoa-34` **starts with a spike test**. If it fails, router mode stays the default and route names get a `hyperadmin-` prefix instead |
| htmx 1.9.10 ignores `HX-Redirect` on a 401 | Medium / Medium | Pinned by an e2e test. Fallback: status 200 plus `HX-Redirect` |
| Default-on CSRF breaks custom templates or scripts | Medium / Medium | `report` mode, an upgrade note, and `_base.html` `hx-headers` covering every built-in view |
| The route-order change hides a route | Low / Medium | Only routes inside the admin router are reordered. A unit test asserts the registration order |
| `register_url_convertor` is global | Low | The key is namespaced (`hyperadmin_pk`) and registered idempotently |
| Moving a JWT into a cookie widens exposure | Low / High | Opt-in only. The cookie is `HttpOnly`, scoped to the admin path, `SameSite=Lax`, `Secure` and covered by CSRF |
| The permissive default when `has_permission` is omitted | Medium / High | Startup `WARNING` and docs (Owner decision 3) |
| Two auth mechanisms (middleware and dependency) drift apart | Medium / Low | They share the route class and the `request.state` keys. Convergence is deferred |
| Scope bleed between nested session middleware | Low / High | Save and restore the host's session, with a dedicated test |
| The sqlmodel matrix: 0.0.19 on the lowest-direct run, ≥0.0.47 on highest | Medium / Medium | `poe deps:bump` across 3 combinations, with explicit column types in tests |
| Visual baseline drift (datetimes, links under `/admin/static`) | High / Low | Refresh the baselines in the stories that change the UI. Never `--no-verify` |
| pydantic-settings lower bound vs `pydantic>=2.7` on Python 3.10 lowest-direct | Medium / Medium | Checked by `poe deps:bump` (Open Question 1) |
| Stories collide in `dynamic.py`, `routing.py` and `core/app.py` | High / Low | `Blocked by` ordering, one PR per story, rebase before push |

## Rollout

1. **Security fix first:** `st-v058-byoa-10` ships as a standalone `fix(views)` PR if Owner decision 4 is accepted.
2. **Packaging hygiene** (`st-v058-byoa-11`, `st-v058-byoa-12`) can land as soon as this SDD is approved. It has no runtime risk.
3. **Pillars A to D** are built bottom-up in the order of the Story breakdown. Each story is one PR against `develop` and must pass `poe lint`, `poe test:unit` and, for UI stories, `poe test:e2e`.
4. **Remove the sqlmodel cap** (`st-v058-byoa-48`) once the datetime, form and template stories are merged.
5. **Publish `0.5.0a1`** to PyPI as a pre-release (`st-v058-byoa-50`), after the owner has set up the trusted publisher. `develop` merges into `master`, `release.yml` tags the release and creates a GitHub pre-release, and `publish.yml` builds, smoke-tests and publishes.
6. **Docs and example** (`st-v058-byoa-51`): the guide "Add HyperAdmin to an existing FastAPI app", plus `examples/byoa/`, which has JWT host auth, UUID and string keys, its own lifespan, `/static` and a `session` cookie.
7. **Dogfood-1** (`st-v058-byoa-52`): install `hyper-admin==0.5.0a1` from PyPI into a real, pre-existing application (not named in this repo), following only the guide and timing it.
   - Every friction point is filed as a framework-neutral story.
   - Blockers are fixed in v0.5.8 and released as `0.5.0a2`, and so on.
   - The milestone closes when the guide can be completed in 10 minutes or less with no blockers.

## BDD Scenarios

### Keys

```
Scenario: UUID primary key detail page renders
  Given a SQLModel Document with id: uuid.UUID = Field(default_factory=uuid4, primary_key=True) is registered
  And   a Document row exists
  When  the user requests GET /admin/document/{that uuid}
  Then  the response status is 200
  And   the detail fields show the document

Scenario: malformed UUID in the URL returns 404
  Given the Document model with a UUID primary key is registered
  When  the user requests GET /admin/document/not-a-uuid
  Then  the response status is 404

Scenario: natural string primary key is editable on create
  Given a model Country with code: str = Field(primary_key=True) and no default
  When  the user opens /admin/country/create
  Then  the form shows a required code field

Scenario: natural string primary key is not rendered on the update form
  Given a Country row with code "NL"
  When  the user opens /admin/country/NL/edit
  Then  the form has no code input

Scenario: updating a UUID row does not change its primary key
  Given a Document row with id U
  When  the user submits the edit form with a new title
  Then  the row with id U has the new title
  And   no row with a different id was created

Scenario: string primary key with special characters round-trips through URLs
  Given a Country row whose code is "a b?c"
  When  the user clicks its View link in the list
  Then  the detail page for "a b?c" returns 200

Scenario: the create-popup route is not captured by the string-pk detail route
  Given the Country model with a string primary key and can_create=True
  When  the user requests GET /admin/country/create-popup?target=country
  Then  the popup form fragment is returned with status 200

Scenario: bulk action runs on UUID rows
  Given two Document rows and a bulk action "archive"
  When  the user posts both UUIDs as ids to the bulk endpoint
  Then  the bulk result shows two rows with status "ok"

Scenario: inline edit works on a UUID row
  Given list_editable=["title"] on Document
  When  the user saves a new title in the inline editor for a row
  Then  the cell shows the new title with the saved flag

Scenario: FK choices use the target model's UUID primary key
  Given Attachment.document_id references a UUID-keyed Document
  When  the choices endpoint for document is requested
  Then  each option value is the canonical UUID string of a Document

Scenario: popup create returns a UUID string id
  Given the Document model with a UUID primary key
  When  the popup form is submitted with valid data
  Then  the HX-Trigger payload hyperadminPopupCreated.id is the new UUID as a string

Scenario: popup create keeps a numeric id for int primary keys
  Given an int-id model
  When  the popup form is submitted with valid data
  Then  the HX-Trigger payload id is a JSON number

Scenario: existing int-id admin keeps identical URLs and test ids
  Given an int-id model Product with a row whose id is 7
  When  the list page is rendered
  Then  the View link href is /admin/product/7
  And   the edit button's data-testid is cell-edit-name-7

Scenario: composite primary key model is registered list-only
  Given a model with a two-column primary key
  When  the admin generates routes
  Then  only the list and choices routes exist for that model
  And   a warning is logged
```

### Datetimes

```
Scenario: aware datetime column accepts datetime-local input in the display timezone
  Given HYPERADMIN_TIMEZONE=Europe/Amsterdam
  And   an Event.starts_at column of kind aware
  When  the user submits 2026-07-01T10:00 in the create form
  Then  the stored value is 2026-07-01T08:00:00+00:00

Scenario: aware datetime renders in the display timezone
  Given HYPERADMIN_TIMEZONE=Europe/Amsterdam
  And   an Event with starts_at=2026-07-01T08:00Z
  When  the user opens the edit form
  Then  the starts_at input value is 2026-07-01T10:00:00

Scenario: naive datetime column is stored as entered
  Given a column typed DateTime(timezone=False)
  When  the user submits 2026-07-01T10:00
  Then  the stored value is the naive datetime 2026-07-01 10:00

Scenario: invalid datetime input shows a field error
  Given an Event create form
  When  the user submits "not-a-date" for starts_at
  Then  the starts_at-errors list shows "Enter a valid date/time"

Scenario: unchanged datetime keeps its microseconds on update
  Given an Event with starts_at having microseconds
  When  the user edits only the title and saves
  Then  starts_at is unchanged including microseconds

Scenario: built-in User creation works on sqlmodel 0.0.45 or newer
  Given sqlmodel >= 0.0.45 is installed and built-in auth is enabled
  When  createsuperuser runs
  Then  a user row is inserted
  And   its created_at reads back as an aware UTC datetime

Scenario: auto-now field with a tz-aware lambda is hidden from forms
  Given a field created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
  When  the create form is rendered
  Then  created_at is not an input

Scenario: per-request timezone override
  Given the host middleware sets request.state.hyperadmin_timezone = ZoneInfo("Asia/Tokyo")
  When  an aware datetime is rendered in the list
  Then  it is shown in Asia/Tokyo time
```

### Auth bridge

```
Scenario: bridge admits a host-authenticated staff user
  Given Admin(auth=ExternalAuth(get_user=dep, can_access=is_admin)) mounted at /admin
  And   dep resolves a host User(id=UUID(...), role="admin") from "Authorization: Bearer t1"
  When  GET /admin/ is requested with that header
  Then  the response is 200
  And   the navbar shows the host user's display name

Scenario: bridge redirects an anonymous browser to the host login URL
  Given ExternalAuth(login_url="/login") and dep returns None
  When  GET /admin/order?page=2 is requested without credentials
  Then  the response is 303 to /login?next=%2Fadmin%2Forder%3Fpage%3D2

Scenario: host dependency raising 401 is treated as anonymous
  Given dep uses OAuth2PasswordBearer(auto_error=True)
  When  GET /admin/ is requested without an Authorization header
  Then  the response is 303 to the configured login_url

Scenario: anonymous HTMX request gets HX-Redirect instead of a swapped login page
  Given ExternalAuth(login_url="/login") and dep returns None
  When  a request with header HX-Request: true hits DELETE /admin/order/5
  Then  the response is 401 with header HX-Redirect=/login?next=...

Scenario: authenticated user failing can_access is forbidden
  Given can_access returns False for user "bob"
  When  bob requests GET /admin/
  Then  the response is 403
  And   no redirect to login_url occurs

Scenario: has_permission callable gates model actions
  Given has_permission(user, "delete_order") returns False
  When  the user sends DELETE /admin/order/5 with a valid CSRF token
  Then  the response is 403

Scenario: object permission checker receives the host user object
  Given AdminOptions(object_permission_checker=owner_only) on Order
  And   the host user does not own order 42
  When  GET /admin/order/42 is requested
  Then  the response is 403
  And   the checker was called with the host User instance

Scenario: bridge mode creates no hyperadmin tables
  Given a fresh interpreter importing hyperadmin and hyperadmin.auth.bridge only
  When  Admin(auth=ExternalAuth(...)).mount("/admin") runs and startup completes
  Then  SQLModel.metadata has no table named hyperadmin_users
  And   the sidebar shows no User, Group or Permission entries

Scenario: built-in auth models stay registered for auth_backend users
  Given Admin(auth_backend=SessionAuthBackend(engine)) with default settings
  When  the admin is mounted
  Then  User, Group and Permission admins are registered

Scenario: auth and auth_backend together are rejected
  Given both auth=ExternalAuth(...) and auth_backend=SessionAuthBackend(engine)
  When  Admin(...) is constructed
  Then  ValueError is raised naming both parameters

Scenario: token handoff sets an admin-scoped HttpOnly cookie
  Given ExternalAuth(token_cookie=TokenCookie()) at /admin
  When  POST /admin/auth/session is sent with Authorization: Bearer <valid jwt>
  Then  the response sets hyperadmin_token with HttpOnly, SameSite=Lax and Path=/admin
  And   a subsequent GET /admin/ with only that cookie returns 200

Scenario: token handoff rejects an invalid token
  Given the host dependency rejects "Bearer bad"
  When  POST /admin/auth/session is sent with that header
  Then  the response is 401
  And   no cookie is set

Scenario: explicit Authorization header wins over the token cookie
  Given a hyperadmin_token cookie for user A
  When  GET /admin/ is sent with Authorization: Bearer <token for B>
  Then  request.state.user is B

Scenario: inline cell save enforces change permission
  Given the user lacks change_order
  When  POST /admin/order/5/inline/status is sent with a valid CSRF token
  Then  the response is 403
  And   the field is unchanged

Scenario: realtime SSE works with a UUID principal
  Given realtime is enabled and a bridged user has a UUID id
  When  GET /admin/realtime/sse is requested
  Then  a connection is registered under that UUID key

Scenario: websocket from a foreign origin is closed
  Given realtime is enabled with built-in auth
  When  a WS handshake arrives with Origin: https://evil.example
  Then  the socket is closed with the unauthorized code
```

### CSRF

```
Scenario: HTMX unsafe request without a CSRF token is rejected
  Given a logged-in built-in session user
  When  DELETE /admin/order/5 is sent with HX-Request and no X-CSRF-Token header
  Then  the response is 403 with X-HyperAdmin-CSRF: failed
  And   order 5 still exists

Scenario: HTMX request carrying the rendered token succeeds
  Given the list page was rendered with body hx-headers containing the token
  When  the delete button issues DELETE /admin/order/5
  Then  the response is 200
  And   order 5 is deleted

Scenario: plain form post uses the hidden csrf field
  Given the login page rendered a hidden csrf_token input
  When  POST /admin/login is sent with valid credentials and that field
  Then  the response is 302 to /admin/

Scenario: login CSRF is blocked
  Given no hyperadmin_csrf cookie in the browser
  When  a cross-site form POSTs /admin/login with attacker credentials
  Then  the response is 403
  And   no session is created

Scenario: cross-site Origin is rejected even with a matching token pair
  Given a valid cookie and token pair
  When  POST /admin/order is sent with Origin: https://evil.example
  Then  the response is 403

Scenario: CSRF report mode logs but allows
  Given HYPERADMIN_CSRF_MODE=report
  When  POST /admin/order is sent without a token
  Then  the request is processed
  And   a WARNING log record mentioning csrf is emitted

Scenario: CSRF is off for admins without auth
  Given Admin() with no auth_backend and no auth
  When  POST /admin/order is sent without a token
  Then  the response is not 403
```

### Mount, lifecycle, engine

```
Scenario: admin mount leaves host routes untouched
  Given a host FastAPI app with GET /health and HyperAdmin mounted at /admin
  When  a client requests GET /health
  Then  the response has no Content-Language header
  And   no hyperadmin_session cookie is set

Scenario: host static mount keeps working
  Given a host app that mounts /static named "static" before Admin(app).mount("/admin")
  When  a client requests the host's /static/app.css and the admin dashboard
  Then  /static/app.css returns the host file
  And   the dashboard links its stylesheet from /admin/static/css/hyperadmin.css

Scenario: admin routes are absent from the host OpenAPI schema
  Given HyperAdmin mounted at /admin in isolated mode
  When  a client requests GET /openapi.json
  Then  no path starts with /admin

Scenario: /administrator is not treated as an admin path
  Given built-in auth at /admin in router mode
  When  GET /administrator is requested
  Then  no redirect to /admin/login occurs

Scenario: admin session cookie is scoped to the admin prefix
  Given built-in auth is enabled and the admin is mounted at /admin
  When  a user logs in successfully
  Then  the Set-Cookie header names hyperadmin_session with Path=/admin

Scenario: host session is not overwritten by the admin session
  Given the host installs its own SessionMiddleware with cookie "session"
  When  a user logs in to /admin/login
  Then  the host "session" cookie is not modified

Scenario: tables are not created by default
  Given Admin is built with a host engine and default settings
  When  the application starts
  Then  no CREATE TABLE statement is executed

Scenario: demo mode still works zero-config
  Given Admin(app) is built with no engine and no session factory
  When  a client requests GET /admin/
  Then  the response status is 200

Scenario: permission sync runs under a host lifespan
  Given a host app created with FastAPI(lifespan=host_lifespan) and built-in auth
  When  the first request hits /admin/
  Then  the permission table contains view/add/change/delete rows for each registered model

Scenario: host session factory is used for admin queries
  Given Admin is built with session_factory=host_sessionmaker
  When  the user list page is requested
  Then  the host session factory has been called

Scenario: importing hyperadmin creates no engine
  Given a fresh interpreter
  When  import hyperadmin runs
  Then  create_async_engine has not been called

Scenario: init-db creates only hyperadmin tables
  Given an empty database and host SQLModel models imported
  When  hyperadmin init-db --database-url URL runs
  Then  only hyperadmin_* tables exist

Scenario: uploads require authentication
  Given built-in auth is enabled and a file "a.pdf" exists in storage
  When  an anonymous client requests GET /admin/uploads/a.pdf
  Then  the response is a redirect to /admin/login

Scenario: uploads are not served at the host root
  Given file storage is configured
  When  a client requests GET /uploads/a.pdf
  Then  the response status is 404

Scenario: uploaded SVG is downloaded, not rendered
  Given an authenticated user and an uploaded file "x.svg"
  When  the user requests GET /admin/uploads/x.svg
  Then  the response has Content-Disposition attachment and X-Content-Type-Options nosniff

Scenario: path traversal on uploads is rejected
  Given an authenticated user
  When  the user requests GET /admin/uploads/..%2F..%2Fetc%2Fpasswd
  Then  the response status is 404
```

### Errors, filters, i18n, packaging

```
Scenario: list view surfaces a database error
  Given the table for model Invoice does not exist
  When  an authenticated user opens /admin/invoice
  Then  the page shows the list-error banner mentioning migrations
  And   an ERROR log record with the traceback is emitted

Scenario: integer filter is coerced
  Given Order has list_filter ["quantity"]
  When  the user requests /admin/order?filter_quantity=3
  Then  only orders with quantity 3 are listed

Scenario: date range filter
  Given Order has list_filter ["created_at"]
  When  the user requests /admin/order?filter_created_at__gte=2026-01-01&filter_created_at__lte=2026-01-31
  Then  only orders created in January 2026 are listed

Scenario: UUID filter with an invalid value shows an error
  Given Order has list_filter ["customer_id"] of type UUID
  When  the user requests /admin/order?filter_customer_id=not-a-uuid
  Then  the response status is 200
  And   the filter-error element names the customer_id field

Scenario: filtering on a non-whitelisted column is ignored
  Given User has list_filter ["is_active"]
  When  the user requests /admin/user?filter_password_hash=abc
  Then  all users are listed

Scenario: validation message is translated
  Given the request locale is "uk" and a field constrained gt=5
  When  the user submits the create form with value 3
  Then  the field error list shows the Ukrainian translation of "Input should be greater than 5"

Scenario: built wheel imports cleanly
  Given the wheel produced by uv build installed in a fresh venv
  When  python -c "from hyperadmin import Admin" runs
  Then  it exits 0
```

## Story breakdown

Stories live in `.meta/epics/epic-v058-bring-your-own-app/stories/`.
- Every implementation story is **blocked by `st-v058-byoa-00`**, the human gate for this SDD. The only possible exception is `-10`, if Owner decision 4 is accepted.
- Stories are ordered bottom-up: packaging, then domain, then logic, then views, then UI, then release.
- These stories supersede the re-cut stubs `st-v058-byoa-01` to `-07` from `chore/meta-roadmap-recut`, which should be deleted when that branch merges.

| ID | Title | Size | Layer | Blocked by |
|---|---|---|---|---|
| 00 | review(spec): approve BYOA SDD | S | gate | — |
| 10 | fix(views): enforce model + object permissions on inline edit/save, update form, file delete, single actions | S | views | 00* |
| 11 | chore(deps): audit runtime deps (add pydantic-settings, tzdata on win32; drop appnope/uvicorn/httpx; fastapi[standard]→fastapi; dedupe python-multipart) | S | packaging | 00 |
| 12 | build: commit uv.lock, `uv sync --locked` in CI, gate PRs to master/develop | S | packaging | 11 |
| 13 | feat(core): PrimaryKeyInfo codec + InvalidPrimaryKey + BaseAdapter.pk/datetime_kind | S | domain | 00 |
| 14 | feat(core): timezones module + settings.timezone | M | domain | 00 |
| 15 | feat(adapters): introspection — introspect_primary_key, datetime_kind, coerce_column_value | M | domain | 13, 14, 19 |
| 16 | fix(auth): tz-aware auth timestamps via UTCNaiveDateTime + utc_now | S | domain | 14 |
| 17 | refactor(auth): lazy auth package exports + auth.metadata() | S | domain | 00 |
| 18 | feat(core): AdminAuthenticationRequired/AdminAccessDenied + CsrfTokenSigner | S | domain | 00 |
| 19 | feat(core): typed filter coercion and FilterCondition (core/filtering.py) | M | domain | 14 |
| 20 | refactor(db): lazy default engine; deprecate hyperadmin.db.engine | S | domain | 00 |
| 21 | feat(core): session_factory seam on BaseAdapter, adapters and auth services | M | domain | 20 |
| 22 | refactor(adapters): pk-agnostic get/get_related/update/delete/get_choices/save_inline_rows | M | logic | 15, 21 |
| 23 | refactor(core): pk-aware display name, FK filter choices, list_display fallback, inline display fields | S | logic | 13 |
| 24 | feat(adapters): apply FilterCondition lists (exact/gte/lte/in/isnull) with dict back-compat | S | logic | 19, 22 |
| 25 | feat(auth): ExternalAuth, TokenCookie, CallablePermissionChecker, build_admin_dependency | M | logic | 17, 18 |
| 26 | feat(core): lifecycle — opt-in create_tables, startup/shutdown/lifespan, first-request guard, init-db CLI | M | logic | 17, 21 |
| 27 | feat(i18n): translate Pydantic validation messages by error type (#531) | M | logic | 00 |
| 28 | feat(routing): per-model pk convertor, hyperadmin_pk convertor, literal routes first, composite list-only | M | views | 15 |
| 29 | refactor(views): DynamicModelView item handlers use self.pk and _resolve_pk (404 on invalid) | M | views | 10, 22, 23, 28 |
| 30 | refactor(views): bulk ids, single actions and popup payload are pk-type-agnostic | S | views | 29 |
| 31 | refactor(forms): pk-aware PydanticForm (natural pk on create) and InlineFormset pk codec | M | views | 29 |
| 32 | feat(forms): tz-aware datetime parsing, Aware/NaiveDatetime, broadened auto-now, preserve unchanged | M | views | 31 |
| 33 | feat(views): template filters ha_pk/ha_dom_token/ha_datetime_input/ha_display + timezone plumbing | S | views | 13, 14 |
| 34 | feat(views): namespace-aware url helper and Jinja url_for override (spike first) | S | views | 30 |
| 35 | feat(core): isolated sub-application mount (scoped middleware, static/ws under prefix, router legacy mode) | M | views | 26, 34 |
| 36 | feat(auth): admin-scoped session cookie via AdminSessionMiddleware | M | views | 35 |
| 37 | fix(uploads): serve uploads under the admin prefix behind auth with nosniff/attachment policy | M | views | 35 |
| 38 | feat(views): HyperAdminRoute route class — auth-error translation and token-cookie bridging | M | views | 18, 35 |
| 39 | feat(views): CsrfGuard signed double-submit wired into HyperAdminRoute and settings | M | views | 38 |
| 40 | feat(core): Admin(auth=ExternalAuth) wiring + register_auth_models opt-in | M | views | 25, 39 |
| 41 | feat(auth): token handoff POST /auth/session and bridge logout | M | views | 40 |
| 42 | feat(realtime): hashable user keys, bridge-aware SSE/WS, WS Origin check | S | views | 40 |
| 43 | fix(views): list_view logs and surfaces DB errors | S | views | 29 |
| 44 | feat(views): typed, whitelisted filters in list_view | S | views | 24, 43 |
| 45 | feat(templates): pk-agnostic links/testids and tz-aware datetime rendering | M | ui | 32, 33 |
| 46 | feat(ui): CSRF token injection (hx-headers, meta, csrf_input) + bridge-aware navbar | M | ui | 39, 40 |
| 47 | feat(ui): range inputs and filter errors in the filter bar | M | ui | 44 |
| 48 | build(deps): lift sqlmodel<0.0.45 cap; migrate examples/fixtures to utc_now; refresh baselines | S | ui | 16, 32, 45 |
| 49 | test(e2e): pk-type and timezone fixture app (UUID, natural str, int) | M | ui | 30, 45, 48 |
| 50 | build(release): 0.5.0a1, pep440 commitizen, __version__, fixed release/publish workflows | M | packaging | 12, 48 |
| 51 | docs(guides): existing-app guide + examples/byoa + CSRF upgrade note + multi-tenancy SDD amendment | M | ui | 36, 37, 41, 42, 46, 47, 49 |
| 52 | chore(dogfood): dogfood-1 on a real existing app from the PyPI alpha; gap log | S | gate | 50, 51 |

\* `-10` may be unblocked early if Owner decision 4 is accepted.

## Open Questions

These are lower-stakes than the Owner decisions. Each has a proposed answer that the implementer applies unless the reviewer says otherwise.

- [ ] **1. The pydantic-settings lower bound.** Raise it to the version that fixes GHSA-4xgf-cpjx-pc3j (≥2.14.2 per the current `pyproject.toml` comment), provided `poe deps:bump` stays green on Python 3.10 lowest-direct. Otherwise use `>=2.3` and keep the ignore.
- [ ] **2. Validating the token handoff.** Options: an internal sub-application call to the host dependency (proposed), or requiring an explicit `verify_token` callable. The fallback is `verify_token` if the sub-app call proves brittle.
- [ ] **3. Pillow.** Keep it as a hard runtime dependency (proposed for 0.5.0a1), or move it to a `hyper-admin[images]` extra later.
- [ ] **4. Reserved path segments for `str` keys** (`create`, `choices`, …). Document them only (proposed), or reject such values when a row is created.
- [ ] **5. The popup `HX-Trigger` id.** Keep it a number for int keys (proposed, for back-compat), or always send a string.
- [ ] **6. `create_tables=True` semantics.** Keep today's "create everything in the metadata" behaviour (proposed, for back-compat) or narrow it to `hyperadmin_*` tables.
- [ ] **7. Converging built-in auth onto the route dependency**, including redesigning the MFA gate. Deferred to a later milestone. Recorded here so the v0.5.3 and v0.5.2 SDDs account for both modes.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Detect primary keys through the SQLAlchemy mapper (`PrimaryKeyInfo`) | Handles any attribute name, `sa_column` remapping, UUID and `str` keys, and composite detection | Hard-coded `id` with a `pk_field` option (manual, error-prone) |
| Per-model path converter (`int`, `uuid`, `hyperadmin_pk`) | Int URLs stay byte-identical. A malformed UUID returns 404 at match time | One `str` converter for all models (breaks int 404 semantics and the route order) |
| Primary keys immutable after create | Prevents an inline `uuid4` from overwriting the key, and avoids cascading key updates | Renameable natural keys (cascades, dangling links) |
| `UTCNaiveDateTime` for the auth models | No migration. Safe with asyncpg. Aware values on both sides of the sqlmodel cap | Switch to `timestamptz` (needs a migration); keep `datetime.now` (breaks on ≥0.0.45) |
| A single display timezone setting plus a per-request override | Simple, and lets the host or bridge choose per user | Store a timezone per user (a schema change) |
| Auth bridge as a route-level `Depends` | Native FastAPI resolution, host test overrides work, scoped to the admin | Middleware calling private `solve_dependencies`; a `CurrentUserProvider` protocol (too much friction) |
| Custom `APIRoute` class | The only admin-scoped place to catch host 401s and do body-aware CSRF | An app-wide exception handler or middleware (invasive) |
| Built-in auth stays on middleware for now | Zero regression for the MFA partial-auth gate | Migrate now (too large for one milestone) |
| Signed double-submit CSRF cookie | Needs no server session, so it works in bridge mode | A token stored in the session (needs `SessionMiddleware`); Origin-only checks (weak) |
| `register_auth_models` and the other scalar options in settings | Follows the settings rule: scalar config lives in `HyperAdminSettings` | `Admin(include_auth_models=...)` |
| Isolated sub-app as the default mount | The only way to scope Starlette middleware, cookies and route names without the host's cooperation | A router plus path-checking middleware (still global) |
| Jinja `url_for` override with fallback from namespaced to plain names | No edits to about 25 template call sites; host template overrides keep working | A new `admin_url` global (touches every template) |
| A first-request startup guard | Works under any host lifespan without the host changing code | Require composing the lifespan (fails the 10-minute thesis) |
| `create_tables=False` by default, with a demo-mode exception | Never issue DDL against a host database behind Alembic's back; zero-config demos still work | Keep `True` (unsafe in production) |
| URL filters limited to `list_filter` | Closes the equality oracle on secret columns | Allow every column (the status quo) |
| Uploads served through an authenticated route | Allows auth, a header policy and traversal checks | `StaticFiles` inside the sub-app (no header control) |
| First release versioned `0.5.0a1` on PyPI | Honest pre-release that dogfooding can install; decoupled from roadmap labels | `0.1.0` (misleading); wait for 1.0 (blocks dogfooding) |
| `DeclarativeBase` adapter deferred | Keeps the milestone focused on SQLModel hosts, which the dogfood apps are | Include it (doubles the adapter test matrix) |

---

## Appendix A: audit of int-pk and `id` assumptions

This appendix was compiled for pillar A. Line numbers are from `f96dcc0`.

- **`routing.py`**
  - 105, 113, 119, 127, 133, 141, 172, 199: `{item_id:int}`.
  - 147–196: literal routes registered after the item routes.
- **`adapters/sqlmodel.py`**
  - 43, 189: `self.model.id`.
  - 153, 170: uncoerced `session.get`.
  - 233–235: raw cascade filter values.
  - 253: `getattr(item, "id")`.
  - 279: truthy `_pk` check.
  - 141–160: `update()` writes key attributes.
- **`adapters/sqlalchemy.py`**
  - 34–37: `primary_key[0]`, uncoerced.
  - 105, 116, 127, 197, 220: same issues as the SQLModel adapter.
  - 103–112: `update()` writes key attributes.
- **`core/`**
  - `display.py:64`
  - `discovery.py:89`
  - `introspection.py:153,162`
  - `inlines.py:57`
  - `bulk_results.py:26`: docs only.
  - `actions.py:57,73`: docs only.
  - `core/settings.py:31` is a false positive: `"id"` there is the Indonesian locale.
- **`views/dynamic.py`**
  - 111, 250–263, 268, 329, 364/371, 683–689, 701/710, 750, 775–848 (838 `model_dump` includes a new UUID), 860.
  - 1029–1034: popup `json.dumps` of a UUID.
  - 1115–1135, 1173–1180, 1184–1200, 1231–1303, 1321–1332, 1342–1356.
  - 1374–1386: `_parse_ids` `int()` silently drops UUIDs.
  - 1391–1436, 1454, 1462.
- **`views/forms.py`**
  - 377 and 774: `ann is datetime`.
  - 384–395: `_is_auto_now_field`.
  - 405: skips `"id"`.
  - 479–499: no datetime localisation.
  - 537, 589, 620, 653, 660, 677, 744.
- **`realtime/`**
  - `registry.py:34,61-62`
  - `sse.py:41`
  - `ws.py:51`
  - `_debug.py:31`: `sorted` fails on mixed key types.
- **`auth/`**
  - `models.py:26,59,89`
  - `session.py:39`, `session.py:51`, `views.py:143,381`, `otp.py:86-185`: these use `user.id` and store it in the JSON session. They apply to built-in auth only. The built-in `User` keeps int ids, and bridge mode uses no session, so they are unchanged.
- **Templates**
  - `components/table.html:16,19,24,27,30`
  - `components/inline_cell.html`
  - `components/inline_editor.html`
  - `components/inline_cell_error.html`
  - `update.html:8`
  - `detail.html:7,14,29`
  - `components/bulk_form.html:5,18`
  - `components/bulk_result.html:7,19,22,33`
  - `widgets/datetime_input.html:6`
