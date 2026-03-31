# SDD: Zero-Config Admin — Auto-Discovery with Smart Defaults

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | Epic B (v0.3.0) |
| Milestone | v0.3.0 — Zero-Config & Auth |
| Created | 2026-03-30 |
| Last updated | 2026-03-30 |

---

## Problem

Setting up HyperAdmin currently requires explicit `site.register()` calls for every model.
For projects with many models this is tedious boilerplate, and `list_display`, `search_fields`,
and `list_filter` default to minimal or empty values even when sensible defaults can be inferred
from the model's field types. The result is a poor out-of-the-box experience.

## Goals

- Mount HyperAdmin in 3 lines of code with no explicit registrations.
- Auto-detect all user-defined SQLModel models via SQLModel's metadata registry.
- Infer `list_display` (3–5 important fields), `search_fields` (string/email fields), and
  `list_filter` (bool/enum/FK fields) from model introspection.
- Allow explicit registrations to override auto-detected defaults.
- Display human-readable field labels (not raw `snake_case`) in list and detail views.

## Non-Goals

- Support for non-SQLModel ORMs in auto-discovery (Django ORM, Tortoise, etc.).
- Auto-generation of form layouts or inline configurations.
- Auto-discovery of models from external packages / installed libraries.
- Migration tooling for upgrading existing explicit registrations.

## BDD Scenarios

```
Scenario: zero-config mount registers all user models
  Given an app with 3 SQLModel table models and no explicit site.register() calls
  When  Admin(app, engine=engine).mount("/admin") is called
  Then  all 3 models appear in site._registry
  And   each model has AdminOptions derived from field introspection

Scenario: auto_discover=False skips discovery
  Given an app with 3 SQLModel models
  When  Admin(app, engine=engine, auto_discover=False).mount("/admin") is called
  Then  site._registry contains only explicitly registered models

Scenario: explicit registration is not overwritten
  Given Product is explicitly registered with AdminOptions(can_delete=False)
  When  Auto-discovery runs
  Then  Product's AdminOptions still has can_delete=False

Scenario: list_display infers key fields
  Given a model with fields: id, name, email, created_at, is_active, bio
  When  infer_list_display(model) is called
  Then  the result contains id, name, email, created_at (≤5 fields)
  And   bio (long text) is excluded

Scenario: search_fields infers string fields
  Given a model with fields: id (int), name (str), email (str), is_active (bool), category_id (int FK)
  When  infer_search_fields(model) is called
  Then  the result contains name and email
  And   id, is_active, category_id are excluded

Scenario: list_filter infers boolean and enum fields
  Given a model with fields: is_active (bool), status (Enum), name (str), category_id (int FK)
  When  infer_list_filter(model) is called
  Then  the result contains is_active, status, category_id
  And   name is excluded

Scenario: field name user_id renders as label "User"
  Given a model with a FK field named user_id
  When  the list view renders the column header
  Then  the header displays "User" not "user_id"

Scenario: field name created_at renders as label "Created At"
  Given a model with a field named created_at
  When  the list view renders the column header
  Then  the header displays "Created At"
```

## Design

### Architecture

New module: `src/hyperadmin/core/introspection.py`

Affected modules:
- `core/introspection.py` (new) — field metadata + smart-default inference
- `core/app.py` — `auto_discover` param + `_auto_register_models()`
- `core/options.py` — `list_display: list[str] | None`, `search_fields: list[str] | None`
- `views/dynamic.py` — resolve `None` options via introspection at render time
- `core/display.py` — improved label generation (`user_id` → `"User"`). Currently contains only
  `get_display_name()` for instance-level display. Field-level label logic currently lives in
  `views/forms.py` (line ~537) and `core/discovery.py:29`. This work consolidates field-label
  generation into `core/display.py`, superseding the inline label logic in those two locations.

Dependency flow (no new circular imports):

```
core/introspection.py  (pure, no HTTP, no ORM writes)
         │
         ▼
core/app.py  ──uses──►  core/introspection.py
core/options.py  ──used by──►  routing.py  ──used by──►  views/dynamic.py
```

`core/introspection.py` imports only from `sqlalchemy` (inspection only — no writes).
It must NOT import from `views/`, `auth/`, or `adapters/`.

### Data Model Changes

No new database tables. `AdminOptions` gets two new optional fields:

```python
class AdminOptions(BaseModel):
    list_display: list[str] | None = None   # None = infer; [] = show nothing
    search_fields: list[str] | None = None  # None = infer; [] = disable search
    # existing fields unchanged
```

Existing code passing explicit `list_display=["id", "name"]` is unaffected (not None).

### API / Protocol Changes

`Admin.__init__()` gains one new parameter:

```python
def __init__(
    self,
    app: FastAPI,
    auto_discover: bool = True,   # NEW — default on for zero-config
    ...
)
```

New public functions in `core/introspection.py` (exported via `core/__init__.py`):

```python
def get_field_metadata(model: type) -> dict[str, FieldMeta]: ...
def infer_list_display(model: type) -> list[str]: ...
def infer_search_fields(model: type) -> list[str]: ...
def infer_list_filter(model: type) -> list[str]: ...
```

New internal function in `core/app.py`:

```python
def _auto_register_models(self) -> None: ...  # called from mount()
```

### Configuration Changes

`Admin(auto_discover=True)` — default `True` for zero-config. Opt out with `False`.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Model already registered (explicit) | Skip silently in `_auto_register_models()` |
| Model has no string fields | `infer_search_fields()` returns `[]` |
| Model has no bool/enum/FK fields | `infer_list_filter()` returns `[]` |
| Model with only `id` field | `infer_list_display()` returns `["id", "__str__"]` |
| HyperAdmin internal models (User, Group, etc.) | Filtered out by module prefix check |
| SQLModel abstract models (no `table=True`) | Excluded from discovery |
| `infer_list_display()` on model with >5 candidate fields | Return top 5 by priority |
| `list_display=[]` (explicit empty) | Respected — no columns shown, no inference |

## Migration & Backward Compatibility

Backward compatible — no migration required.

- **`column_list` coexistence**: The existing list-column mechanism is `admin_class.column_list`,
  an attribute on the admin class resolved in `routing.py:200-203` via `_extract_column_names()`.
  The new `AdminOptions.list_display` is a separate field. Priority resolution order:
  1. Explicit `admin_class.column_list` (if set) — takes precedence (existing behavior preserved).
  2. Explicit `AdminOptions.list_display` (if non-None) — new mechanism.
  3. Introspection via `infer_list_display()` — fallback when both are unset/None.
  `HyperAdminRouter.generate_routes()` must resolve these in this order. `column_list` is NOT
  deprecated in this release — both mechanisms coexist.
- Existing apps with explicit `site.register()` calls are unaffected. Auto-discovery skips
  already-registered models.
- Existing apps that do NOT set `column_list` or `list_display` will now see inferred columns
  instead of the old default `["id", "__str__"]`. This is a UX improvement, not a breaking change.
  If the old behavior is needed: `Admin(auto_discover=False)` or explicit `list_display=[]`.
- `AdminOptions.list_display` is a new field (not a type change). No existing code references it.
  Internal routing code that currently reads `column_list` will gain a None-guard for the new
  `list_display` field.

## Open Questions

None — all resolved. See Decision Log.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| `auto_discover=True` by default | Zero-config means zero config — opt-out, not opt-in | `auto_discover=False` default requires no code change but defeats the feature |
| `list_display=None` means infer, `[]` means empty | Distinguishes "not set" from "intentionally empty" | Single sentinel value; overloading `[]` with "use defaults" would break existing empty-list intent |
| New `core/introspection.py` module | CONSTITUTION: one module = one responsibility. Display inference is not the same as field classification (`core/fields.py`) | Extend `core/fields.py`; rejected — fields.py handles ORM typing, not UX defaults |
| Store SDDs in `docs/specs/` | Separate from `docs/design/` (UI/frontend RFCs) | Same directory; rejected — mixes implementation specs with UI design |
| Filter discovered models by `__module__` prefix | Risk: third-party SQLModel libraries would appear in admin. Filter to models whose `__module__` does NOT start with `hyperadmin`. Third-party models excluded unless explicitly registered. | Filter by app's metadata only; rejected — SQLModel shares a single global metadata registry, no per-app isolation |
| `"__str__"` as a virtual column name in `list_display` | Convention: when `"__str__"` appears in column list, `get_display_name()` is called at render time to produce a human-readable label. This exists in current codebase (`views/dynamic.py:100`) but is undocumented. | Explicit display-name column; rejected — `__str__` convention is simple and already in use |
