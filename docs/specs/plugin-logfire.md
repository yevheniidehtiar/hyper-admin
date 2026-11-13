# SDD: hyperadmin-logfire — Logfire observability plugin

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved (architect) |
| Issue | TBD |
| Milestone | v0.8.0 — Plugins & AI |
| Created | 2026-05-05 |
| Last updated | 2026-11-11 |

---

## Problem

Admin performance problems stay hidden until users complain: slow list queries, N+1 queries,
forms that fail validation over and over. HyperAdmin has no first-party observability story.

The plugin registry (`docs/specs/plugin-registry.md`) has shipped phase 1, the UI seams.
`hyperadmin-reports` and `hyperadmin-tasks` use only those seams. `hyperadmin-logfire` is the
first plugin that needs the **phase 2 lifecycle hooks**, so it is the proof that those hooks are
enough.

If this plugin needs a change to `src/hyperadmin/` beyond the hooks in the registry SDD, the
registry SDD is wrong and gets revised first. That is the design pressure on this work.

### What changed since revision 1 (2026-05-05)

- **Second plugin, not first.** Reports and tasks shipped first on the phase 1 seams
  (registry SDD, Decision Log 2026-10-18).
- **Phase 2 is still not fired.** `Admin.dispatch_hook()` and `LIFECYCLE_HOOKS` exist, but no
  core call site calls them yet. This SDD now splits into phase A (ships on today's core) and
  phase B (needs registry phase 2).
- **Logfire API checked against logfire 5.5.0** (2026-11-07 probe; see Decision Log):
  - `instrument_sqlalchemy(engine=...)` accepts an `AsyncEngine`. SQL spans nest under an open
    `admin.adapter.*` span.
  - A span entered in one sync call and exited in another, bridged by a `ContextVar`, survives
    an `await` in between. That is the `on_before` / `on_after_adapter_call` pattern.
  - Before `logfire.configure()`, logfire itself emits a `LogfireNotConfiguredWarning` and
    records nothing. The plugin's own one-shot warning (revision 1) is redundant and is dropped.
  - The OpenTelemetry SQLAlchemy instrumentation supports `sqlalchemy>=1.0,<2.1` and raises
    `RuntimeError` on 2.1. HyperAdmin allows `sqlalchemy>=2.0.46` and locks 2.0.54.
- **Install path.** The plugins are not on PyPI. Like `hyperadmin-tasks`, users install from a
  git subdirectory until the plugin release pipeline exists.
- **Two new hooks and an error path.** Revision 1 asked for `on_validation_error` and
  `on_auth_event`, but they were never added to the registry SDD, so this PR adds them. It also
  adds an `error` argument to `on_after_adapter_call`: without it, an adapter that raises
  leaves its span open.

## Goals

1. **One-call setup:** `instrument_admin(admin)` turns on HTTP and SQL spans. *(phase A)*
2. **HTTP and SQL spans:** HTTP spans come from FastAPI's native telemetry when the installed
   FastAPI has it (it accepts `FastAPI(telemetry=...)`), else from
   `logfire.instrument_fastapi` on the admin sub-app (`admin.asgi_app`; the host app in router
   mode). SQL spans come from `logfire.instrument_sqlalchemy(engine=admin.engine)`, or from the
   plugin's built-in listeners where that instrumentor cannot instrument the engine
   (SQLAlchemy 2.1, a second engine in the process). Each has an opt-out. *(phase A)*
3. **Adapter spans:** `admin.adapter.<op>` spans with the attributes `model` and `op`, plus
   paging, search and filter context. SQL spans nest under them. They are emitted through
   `on_before_adapter_call` / `on_after_adapter_call`. *(phase B)*
4. **Validation events:** a structured `admin.validation_error` event when an admin form fails
   validation. It carries `model` and the error types per field, never the submitted values.
   *(phase B)*
5. **Auth events:** `admin.auth.login_success`, `admin.auth.login_failure`,
   `admin.auth.logout`, `admin.auth.permission_denied`. *(phase B)*
6. **Never crashes, never drops a supported version:** without `logfire.configure()` it emits
   nothing and raises nothing. Every FastAPI (`>=0.116`) and SQLAlchemy (`>=2.0.46`, including
   2.1) that hyper-admin supports gets HTTP and SQL spans.
7. **No core changes beyond the registry SDD hooks.**

## Non-Goals

- **In-admin performance dashboard widget.** RFC #276 phase 2; deferred to v0.8.1 or later.
- **A generic OpenTelemetry variant (`hyperadmin-otel`).** Logfire already exports OTLP; wait
  for a user whose backend it cannot reach.
- **Sampling, scrubbing and token configuration.** These belong to `logfire.configure()`, which
  the plugin never calls.
- **Custom span attributes per model** (`AdminOptions.observability_attrs`). Users who need it
  wrap their own adapter.
- **`logfire.instrument_pydantic()`.** It traces every Pydantic validation in the process, not
  only admin forms. Too noisy.
- **A root `hyper-admin[logfire]` extra.** This waits until the plugin is on PyPI; an extra
  can't point at a git subdirectory. It goes in its own dependency PR.

## Phasing

| Phase | Scope | Needs core change? |
|---|---|---|
| A — `lf-scaffold` | Package, entry point, `LogfirePlugin` (`on_register` only), `instrument_admin()` (HTTP + SQL), built-in SQL spans for engines the instrumentor cannot take, README, docs page. Unit tests with logfire's `TestExporter`. | No |
| B0 — registry phase 2 (registry epic) | `_AdapterHookWrapper`, CRUD hook call sites, and the two new hooks `on_validation_error` and `on_auth_event`, with their call sites. | Yes, in the registry epic |
| B — `lf-hooks` | Plugin hook methods for adapter spans, validation events and auth events. E2E against a test sink. | No |

Phase A is useful on its own (request and query traces of the admin) and proves the package,
CI and install path before phase B0 touches core.

## BDD Scenarios

```
Scenario: instrument_admin emits HTTP and SQL spans                       (phase A)
  Given logfire is configured with a test exporter
  And   instrument_admin(admin) has been called
  When  GET /admin/product/ is requested
  Then  the exporter holds an HTTP server span for the request
  And   at least one SQL span is a descendant of it

Scenario: instrument_admin falls back to built-in SQL spans on SQLAlchemy 2.1  (phase A)
  Given logfire.instrument_sqlalchemy raises RuntimeError for the installed SQLAlchemy
  When  instrument_admin(admin) is called and GET /admin/product is requested
  Then  no exception is raised
  And   an INFO log record names the SQLAlchemy version
  And   built-in SQL spans ("SELECT <db>", db.system, db.statement) are in the request's trace

Scenario: instrument_admin is a no-op when the plugin is disabled         (phase A)
  Given hyperadmin-logfire is installed
  And   Admin(app, engine=engine, disabled_plugins=["logfire"]) is constructed
  When  instrument_admin(admin) is called and GET /admin/product/ is requested
  Then  neither FastAPI nor SQLAlchemy is instrumented
  And   the exporter holds no SQL spans
  (A FastAPI with native telemetry still records its own HTTP spans; the plugin does not
   control those.)

Scenario: list view emits an adapter span                                 (phase B)
  Given logfire is configured with a test exporter
  And   instrument_admin(admin) has been called
  When  GET /admin/product/ is requested
  Then  the exporter holds a span "admin.adapter.list" with attributes model="Product", op="list"
  And   the list query's SQL span is its child

Scenario: an adapter error closes its span with the exception             (phase B)
  Given the Product adapter's get raises RuntimeError
  When  GET /admin/product/1/ is requested
  Then  the span "admin.adapter.get" is ended
  And   it records the RuntimeError

Scenario: validation failure emits a structured event                     (phase B)
  Given logfire is configured with a test exporter
  When  POST /admin/product/create with price="abc"
  Then  the exporter holds an event "admin.validation_error" with model="Product"
  And   its field_errors attribute maps "price" to a list of error types
  And   the value "abc" appears in no attribute

Scenario: failed login emits an auth event                                (phase B)
  Given logfire is configured with a test exporter
  When  POST /admin/login with username=alice password=wrong
  Then  the exporter holds an event "admin.auth.login_failure" with username="alice"
  And   no attribute contains "wrong"

Scenario: plugin records nothing when logfire is not configured           (phase B)
  Given logfire.configure() was not called
  When  Admin is constructed and GET /admin/product/ is requested
  Then  the response is 200
  And   no exception is raised by a plugin hook
```

Phase B scenarios that need the new core hooks get matching scenarios in the registry SDD's
phase 2 E2E story (hook firing and failure isolation).

## Design

### Architecture

Monorepo subpath `plugins/hyperadmin-logfire/`, same layout as `hyperadmin-tasks`:

```
plugins/hyperadmin-logfire/
  pyproject.toml               # name="hyperadmin-logfire"; deps: hyper-admin, logfire[fastapi,sqlalchemy]>=5,<6
                               # entry point: [project.entry-points."hyperadmin.plugins"] logfire = "hyperadmin_logfire:LogfirePlugin"
  README.md
  src/hyperadmin_logfire/
    __init__.py                # exports LogfirePlugin, instrument_admin
    plugin.py                  # LogfirePlugin: on_register (A); hook methods (B)
    instrument.py              # instrument_admin(), FastAPI-native detection, engine bookkeeping (A)
    sql_spans.py               # built-in SQL spans (SQLAlchemy 2.1, extra engines) (A)
    spans.py                   # ContextVar span bridge and attribute builders, pure functions (B)
  tests/
    conftest.py                # logfire.configure(send_to_logfire=False, console=False, additional_span_processors=[SimpleSpanProcessor(TestExporter())])
    unit/test_instrument.py    # A
    unit/test_spans.py         # B
    e2e/test_spans_e2e.py      # B
```

The root `pyproject.toml` adds `plugins/hyperadmin-logfire` to `[tool.uv.workspace.members]`.
That is a hotspot and dependency change, so it ships in its own small PR before the scaffold
(conflict-avoidance rules).

Dependency flow: `hyperadmin_logfire` → `hyperadmin` (public API only: `Admin`, the `Plugin`
protocol) and `logfire`. Nothing in `hyperadmin` imports the plugin.

### Hook usage

| Plugin behaviour | Hook | Exists today? |
|---|---|---|
| Adapter span open | `on_before_adapter_call(admin, model, op, kwargs)` | Name in `LIFECYCLE_HOOKS`, never fired |
| Adapter span close | `on_after_adapter_call(admin, model, op, result, error)` | Same; `error` is **new in this revision** |
| Validation event | `on_validation_error(admin, model, field_errors)` | **New**; added to the registry SDD by this PR |
| Auth events | `on_auth_event(admin, event, user, username, request)` | **New**; added to the registry SDD by this PR |
| HTTP and SQL spans | none (public Logfire APIs, called from `instrument_admin`) | n/a |

Changes this PR makes to the registry SDD (doc only; the code lands with phase B0):

- `on_after_adapter_call` gains `error: BaseException | None`. `_AdapterHookWrapper` fires it
  in `finally`, with `result=None` and the exception when the call raises, then re-raises.
- `on_validation_error(admin, model, field_errors)` is fired by the `DynamicModelView` create
  and update handlers when the form returns errors. `field_errors` is
  `dict[str, list[str]]` of field name → pydantic error *types* (`"float_parsing"`), never
  input values.
- `on_auth_event(admin, event, user, username, request)` is fired from `auth/views.py` for
  `login_success`, `login_failure` and `logout`, and from the permission check for
  `permission_denied`. `user` is `None` on `login_failure`. The password is never passed.

### API

```python
# hyperadmin_logfire/__init__.py
def instrument_admin(admin: Admin, *, http: bool = True, sql: bool = True) -> None:
    """Instrument the admin's app and engine with Logfire.

    No-op if the plugin is disabled ("logfire" not in admin.plugins). Pass http=False or
    sql=False when the app already calls logfire.instrument_fastapi / instrument_sqlalchemy
    itself, so spans are not recorded twice.
    """

class LogfirePlugin:
    name = "logfire"
    def on_register(self, admin: Admin) -> None: ...                  # phase A: nothing to contribute
    def on_before_adapter_call(self, *, admin, model, op, kwargs) -> None: ...  # phase B
    def on_after_adapter_call(self, *, admin, model, op, result, error) -> None: ...
    def on_validation_error(self, *, admin, model, field_errors) -> None: ...
    def on_auth_event(self, *, admin, event, user, username, request) -> None: ...
```

`on_before_adapter_call` enters a `logfire.span("admin.adapter.{op}", model=..., op=...)` and
pushes it on a `ContextVar` stack. `on_after_adapter_call` pops it, records `error` if any, and
exits it. A stack, not a single slot: an adapter call can nest another one (inline relations).

`instrument_admin` stays explicit, not automatic in `on_register`. It instruments the
**host** app and the user's engine, which is a process-wide effect the user should opt into.
It also lets apps that already instrument FastAPI turn off the duplicate.

### Data Model Changes

No data model changes.

### Configuration Changes

No new `Admin()` parameters and no settings model. Logfire's own configuration
(`logfire.configure()`, `LOGFIRE_TOKEN`, scrubbing, sampling) is the user's.

Install (until the plugin is on PyPI):

```bash
uv add "hyperadmin-logfire @ git+https://github.com/yevheniidehtiar/hyper-admin#subdirectory=plugins/hyperadmin-logfire"
```

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `logfire.configure()` not called | Logfire emits its own `LogfireNotConfiguredWarning` and records nothing. The plugin adds no warning of its own. |
| `logfire` not installed | It is a hard dependency of the plugin, so this cannot happen in a normal install. If the import fails anyway, `PluginRegistry` logs ERROR and skips the plugin (`load_error`). |
| SQLAlchemy ≥ 2.1 (instrumentation refuses it) | `instrument_admin` catches the `RuntimeError`, logs one INFO naming the version, and attaches the plugin's built-in SQL listeners (`sql_spans.py`: SQLAlchemy's public `before/after_cursor_execute` and `handle_error` events, OpenTelemetry API, the instrumentor's span name and `db.*` attributes). We do not pass `skip_dep_check=True`. Verified with SQLAlchemy 2.1.8 installed. |
| App already instruments FastAPI or SQLAlchemy | `instrument_admin(admin, http=False)` or `sql=False`. The README says so. |
| FastAPI with native telemetry (0.143 has it; hyper-admin allows `>=0.116`) | Found while implementing (2026-11-08). FastAPI traces every app itself once `logfire.configure()` sets a tracer provider, and records the full route (`/admin/product`). `logfire.instrument_fastapi(app)` replaces those spans with ASGI ones that only see the `/admin` mount, and calls `suppress_scopes('fastapi')`, which silences FastAPI's native spans **process-wide**. So `instrument_admin` skips `instrument_fastapi` when `FastAPI` accepts `telemetry=`, and on older FastAPI instruments the admin sub-app (`admin.asgi_app`), whose spans carry the admin route (`/product`) instead of the mount (`/admin`); in router mode, the host app. |
| SQLAlchemy instrumentor is a process-wide singleton | A second `instrument()` call is a silent no-op. The plugin remembers the engines it instrumented (weakly); a further admin engine gets the built-in listeners. If the app instrumented SQLAlchemy before the plugin did, the plugin leaves it to the app. |
| `instrument_admin` called twice | Guarded by a flag on the plugin instance; the second call is a no-op. Revision 1 assumed Logfire is idempotent here, which is not verified. |
| Plugin disabled (`disabled_plugins=["logfire"]` or `HYPERADMIN_DISABLED_PLUGINS`) | Hooks never run; `instrument_admin` returns early. |
| Adapter raises between before and after | `on_after_adapter_call` receives `error`, records it, and closes the span (phase B0 fires it in `finally`). |
| `on_after_adapter_call` finds an empty stack | WARNING log, no-op. This happens only if another plugin's `on_before` raised in a way that broke ordering. |
| Validation errors hold user input | Only field names and error types are recorded, never `input` or `ctx` values. |
| Auth event before a user exists | `user=None`; `username` is the submitted name; the password is never a hook argument. |
| A plugin hook raises | The registry logs at ERROR and continues (existing failure isolation); the request is unaffected. |

## Migration & Backward Compatibility

Pure addition, with one contract change to an unfired hook. The `error` argument on
`on_after_adapter_call` changes a hook no core code fires yet and no shipped plugin implements,
so nothing breaks.

## Open Questions

- [x] **Root `[logfire]` extra?** No, not until the plugin is on PyPI (see Non-Goals).
- [x] **Span name prefix:** `admin.*`, matching RFC #276.
- [x] **`instrument_pydantic()`?** No; too noisy (see Non-Goals).
- [x] **Test sink under pytest-asyncio?** `logfire.testing.TestExporter` with a
      `SimpleSpanProcessor` works; verified with logfire 5.5.0. `logfire.testing` imports
      pytest, so it is test-only.
- [x] **Record `username` on `login_failure`?** Yes, by default (see Decision Log, 2026-11-11).
- [x] **CI job for the plugin.** Deferred with justification: the bot token cannot edit
      `.github/workflows`, so the owner adds `plugins/hyperadmin-logfire` to the test and
      type-check lines (same as the owed `hyperadmin-tasks` edits). It blocks only the CI
      story, not the package, hooks or tests.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Monorepo subpath `plugins/hyperadmin-logfire/` | Same as reports and tasks: one CI, one workspace, atomic PRs with core hook changes | Separate repo; premature |
| Split into phase A (no core) and phase B (registry phase 2), 2026-11-07 | HTTP and SQL traces are useful now and prove packaging; the hook wiring is a separate core epic | Wait for phase 2 before starting; nothing ships for weeks |
| Add `on_validation_error` and `on_auth_event` to the registry SDD | Avoids patching `PydanticForm` or sniffing 302s in middleware; observer pattern like the other hooks | Patch `PydanticForm.validate()`, which violates "no core changes"; ASGI middleware, which can't tell login success from any other 302 |
| `on_after_adapter_call` gets `error` and fires in `finally` | Otherwise a raising adapter leaves its span open and the trace is wrong exactly when it matters | A separate `on_adapter_error` hook; one more name for the same moment |
| `ContextVar` **stack** bridges before and after | Async-safe and request-scoped; verified across an `await`; a stack handles nested adapter calls | A single `ContextVar` slot breaks on nesting; a dict keyed by thread breaks under asyncio |
| Drop the plugin's "not configured" warning | Logfire 5.x already warns (`LogfireNotConfiguredWarning`); two warnings for one cause is noise | Keep `_config_check.py` from revision 1 |
| `instrument_admin` is explicit, with `http` / `sql` opt-outs | It touches the host app and the user's engine; apps that already instrument would get duplicate spans | Instrument automatically in `on_register` |
| Catch the SQLAlchemy-version `RuntimeError` instead of `skip_dep_check=True` | Forcing an incompatible instrumentation "may produce no spans or errors" (logfire's words) | Pin `sqlalchemy<2.1` in the plugin, which would cap every user's SQLAlchemy |
| Built-in SQL listeners as the fallback (2026-11-08) | No supported version loses SQL spans; only public SQLAlchemy events and the OpenTelemetry API, so no dependency on the instrumentor's internals | Drive the instrumentor's `EngineTracer` directly (internal API, changes between betas); only warn (SQLAlchemy 2.1 users lose SQL spans) |
| Record field error *types*, not messages or inputs | Messages and `ctx` can echo the submitted value (passwords, personal data) | Record the full pydantic error dicts |
| Leave HTTP spans to FastAPI's native telemetry when it has one (2026-11-08) | Native spans carry the full route and don't suppress other apps' spans process-wide | Always call `instrument_fastapi` (coarser `/admin` route, process-wide suppression); version-pin FastAPI (we don't know the first release with native telemetry, and the `telemetry=` parameter is the public signal) |
| Record `username` on `login_failure`, never the password (2026-11-11, architect) | It makes brute-force patterns visible; Logfire scrubbing owns redaction; trivially reversible | Omit it (loses the main security signal); hash it (unreadable, still personal data) |
| CI workflow edit stays an owner task (2026-11-11, architect) | Bot token lacks `workflow` scope and `.github/**` is a hotspot; package work does not depend on it | Skip CI for the plugin |
