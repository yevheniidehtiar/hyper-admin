# Hook Reference

Lifecycle hooks let a plugin observe what the admin does. A hook is a method on the plugin object,
named after the hook. [Writing a plugin](authoring.md) shows how to add one.

## The contract

- **Keyword arguments.** Every hook except `on_register` is called with keyword arguments only.
  `admin` (the `Admin` instance) is always among them. End each signature with `**kwargs`, so a
  later release can pass an extra argument without breaking your plugin.
- **Synchronous.** Hooks are plain `def` methods and run inside the request, on the event loop,
  before the response is sent. An `async def` hook is not called: it is reported once at `ERROR`
  and ignored.
- **Observers.** Return values are ignored. A hook cannot change or veto an operation.
- **Isolated.** An exception raised by a hook is logged at `ERROR` on the
  `hyperadmin.core.plugins` logger, with the traceback and the `plugin` and `hook` extra fields.
  The other plugins still receive the hook and the request continues as if nothing happened.
- **Optional.** Implement only the hooks you need.

## All hooks

| Hook | Keyword arguments | Fires |
|---|---|---|
| `on_register` | `admin` (positional) | Once, when the plugin is registered. |
| `on_model_register` | `admin`, `model`, `options` | Once for each model registered with the admin. |
| `on_before_create` | `admin`, `model`, `data` | Before the create form's record is written. |
| `on_after_create` | `admin`, `model`, `instance` | After it was written. |
| `on_before_update` | `admin`, `model`, `pk`, `data` | Before the edit form's changes are written. |
| `on_after_update` | `admin`, `model`, `instance` | After they were written. |
| `on_before_delete` | `admin`, `model`, `pk` | Before a record is deleted. |
| `on_after_delete` | `admin`, `model`, `pk` | After it was deleted. |
| `on_before_adapter_call` | `admin`, `model`, `op`, `kwargs` | Before each adapter operation. |
| `on_after_adapter_call` | `admin`, `model`, `op`, `result`, `error` | After each adapter operation, also when it failed. |
| `on_validation_error` | `admin`, `model`, `field_errors` | When a create or edit form fails validation. |
| `on_auth_event` | `admin`, `event`, `user`, `username`, `request` (and `model` for `permission_denied`) | On sign-in, failed sign-in, sign-out and a denied model permission. |

`model` is always the registered model class, not an instance.

## Registration

### `on_register(admin)`

Called once per `Admin`, while `Admin(...)` is constructed (or from
`admin.plugins.register(...)`). It is the only place where a plugin can add pages, sidebar links,
templates, static files and permissions. If it raises, the plugin is skipped and its contributions
are rolled back.

At this point models are usually not registered yet and no route exists. Use `on_model_register`
to react to models.

### `on_model_register(*, admin, model, options, **kwargs)`

`options` is the model's resolved `AdminOptions`.

Fired from `SiteRegistry.register`, after the model is stored, so the hook may read the registry.
Hooks start to be delivered when `admin.mount()` begins:

- models registered before `mount()` (the usual `site.register(...)` calls at import time) are
  delivered once each, at the start of `mount()`, in registration order;
- models registered later are delivered as they are registered.

A registration that fails (the model is already registered) fires nothing. There is no hook for
`unregister`. The registry is shared by the process: with several `Admin` objects, only the one
mounted last receives this hook.

## Create, update and delete

These six hooks fire from the admin's create form, edit form and delete action:

```text
POST create form
  permission check, form validation      (failure: no CRUD hook, see on_validation_error)
  on_before_create(data)
  adapter create                         (on_before_adapter_call / on_after_adapter_call)
  on_after_create(instance)
  inline child rows are saved
```

| Hook | Detail |
|---|---|
| `on_before_create` | `data` is the validated `dict` about to be written, including stored upload paths. |
| `on_after_create` | `instance` is the stored record, with its primary key. Inline child rows are saved after this hook. |
| `on_before_update` | `pk` is the record's primary key. `data` holds the validated values without the primary key and without `None` values. |
| `on_after_update` | `instance` is the updated record. Inline child rows are saved after this hook. |
| `on_before_delete` | Fires after the permission checks, and only if the record exists. |
| `on_after_delete` | Uploaded files of the record are removed after this hook. |

An `after` hook fires only when the write succeeded. If the database rejects the write (a
constraint violation, a concurrent edit detected by optimistic locking, a delete blocked by
referencing rows), the `before` hook has fired and the `after` hook does not. Do not open
something in a `before` hook that only the `after` hook closes; use the adapter-call hooks for
that.

These hooks do **not** fire for writes that bypass the three forms:

- inline cell edits on the list page,
- inline child rows saved with a parent form,
- a related record created from the quick-create dialog,
- clearing an uploaded file,
- bulk actions and your own code that calls an adapter or the database.

The adapter-call hooks see all of these except code that does not go through the admin's adapter.

## Adapter calls

### `on_before_adapter_call(*, admin, model, op, kwargs, **kw)`

### `on_after_adapter_call(*, admin, model, op, result, error, **kw)`

Every data operation of a model view goes through the model's adapter. These two hooks bracket
each call, which makes them the right place for tracing and timing.

`op` is one of:

| `op` | Adapter methods |
|---|---|
| `get` | `get` |
| `list` | `list`, `list_paginated` |
| `create` | `create` |
| `update` | `update` |
| `delete` | `delete` |
| `get_related` | `get_related` |
| `get_choices` | `get_choices` |
| `save_inline_rows` | `save_inline_rows` |
| `get_schema` | `get_schema` |

`kwargs` is a `dict` of the keyword arguments of the call, for example `{"pk": 7}` or
`{"data": {...}}`. Positional arguments, if any, are under the `"args"` key.

`on_after_adapter_call` always fires once `on_before_adapter_call` has, also when the adapter
raised:

- on success, `result` is what the adapter returned and `error` is `None`;
- on failure, `result` is `None` and `error` is the exception (including a cancelled request).
  The exception is raised again after the hook, so the view handles it as usual.

One request can make several adapter calls. Deleting a record, for example, fires `get` (the view
loads the record first) and then `delete`.

The hooks cost nothing when no plugin uses them: at `admin.mount()`, the adapters are wrapped only
if a registered plugin implements at least one of the two hooks. A plugin registered after
`mount()` therefore gets no adapter-call hooks unless another plugin already listened.

Calls an adapter makes internally (saving each inline child row inside `save_inline_rows`) are
not reported separately.

## Validation errors

### `on_validation_error(*, admin, model, field_errors, **kwargs)`

Fires when a submitted create or edit form is rejected and re-rendered with status 422.
No CRUD hook fires for that request.

`field_errors` maps a field name to a list of pydantic error types, for example
`{"name": ["missing"]}`. A date-time the form could not parse is
reported as `datetime_parsing`. The submitted values and the error messages are never passed, so
the argument is safe to log.

When only inline child rows are invalid, the hook still fires and `field_errors` is empty.
Errors found by the database after validation (a unique constraint) do not fire this hook.

## Authentication events

### `on_auth_event(*, admin, event, user, username, request, **kwargs)`

| `event` | When | `user` | `username` |
|---|---|---|---|
| `login_success` | After the session is created by the login form. | The user | Their username |
| `login_failure` | The login form was posted with wrong credentials. | `None` | The username as typed |
| `logout` | After the session is cleared. | The user who signed out, or `None` | Their username, or `None` |
| `permission_denied` | A model view refused the user, just before the 403 response. | The user | Their username |

`request` is the Starlette request. The password is never passed.

`permission_denied` also carries `model`, the model whose view refused the user. The other events
do not, which is one more reason to accept `**kwargs`.

Not reported in this release:

- a sign-in completed with a second factor (MFA): the password step redirects to the challenge
  and no `login_success` follows;
- sign-in and sign-out when the host application owns authentication (`Admin(auth=...)`);
- a denied object-level permission, and denials on plugin pages.

## Order

Within one hook, plugins are called in registration order:

1. plugins discovered through entry points, alphabetically by entry-point name;
2. pages HyperAdmin registers itself (the permission matrix);
3. plugins registered by hand with `admin.plugins.register(...)`, in call order.

The order does not depend on the installation order of the packages. If two packages declare the
same entry-point name, the one whose entry-point value sorts first is loaded and the other is
skipped with a warning.

A failing plugin does not change the order for the others.

## Example: timing adapter calls

```python
import logging
import time
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("hyperadmin_timing")
_started: ContextVar[float] = ContextVar("hyperadmin_timing_started")


class TimingPlugin:
    name = "timing"

    def on_register(self, admin: Any) -> None:
        self.admin = admin

    def on_before_adapter_call(self, **kwargs: Any) -> None:
        _started.set(time.perf_counter())

    def on_after_adapter_call(
        self, *, model: type, op: str, error: BaseException | None, **kwargs: Any
    ) -> None:
        elapsed_ms = (time.perf_counter() - _started.get()) * 1000
        status = "failed" if error is not None else "ok"
        logger.info("%s.%s %s in %.1f ms", model.__name__, op, status, elapsed_ms)
```

The start time lives in a `ContextVar`, not on `self`: one plugin object serves all requests, and
they overlap.
