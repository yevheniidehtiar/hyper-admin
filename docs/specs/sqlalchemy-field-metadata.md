# SDD: Field-Metadata Seam for Plain SQLAlchemy Models

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | #719 |
| Milestone | — (dogfood epic #701) |
| Created | 2026-10-28 |
| Last updated | 2026-10-28 |

---

## Problem

HyperAdmin advertises SQLAlchemy support, but every view assumes the model is a Pydantic class. Field
metadata is read from `Model.model_fields`, form input is validated with `Model.model_validate`, and
rows are serialised with `instance.model_dump()`. Plain SQLAlchemy mapped classes (`DeclarativeBase`,
`DeclarativeBaseNoMeta`, `MappedAsDataclass`, legacy `declarative_base()`) have none of these.

The Polar dogfood spike (#703, Polar `64a08ec`, HyperAdmin develop `8e4a254`) measured the result.
With #715 worked around, all 138 models registered and the admin mounted, and then:

| Page | Result |
|---|---|
| list / search / sort | 137 / 138 crash: `AttributeError: … no attribute 'model_fields'` (`views/dynamic/base.py:428`) |
| create | 127 / 127 crash (`views/dynamic/relations.py:61`) |
| detail / edit | 11 / 11 crash |

`SQLAlchemyAdapter.create()` also calls `self.model.model_validate(data)` and fails the same way.
Every SQLAlchemy target in epic #701 (Polar, Prefect, Phoenix, Airflow, Mealie, Open WebUI,
freqtrade, fastapi_best_architecture, Agenta, SkyPilot) is blocked on this.

### Inventory of Pydantic assumptions

Reads of `model_fields` on an admin model, excluding `settings.model_fields_set` and the Pydantic
action forms in `views/dynamic/actions.py`, which are genuinely Pydantic:

| What is read | Call sites |
|---|---|
| Field **names / order** | `views/static.py` (3), `views/dynamic/update.py`, `views/dynamic/base.py` (`column_list`, `searchable`, `sortable`, first-field fallback), `views/dynamic/list_view.py`, `views/dynamic/inline.py:181`, `core/inlines.py`, `core/options.py:290` (option validation), `filters/base.py:230` |
| **Annotation** | `core/filtering.py:376`, `core/adapters.py:245` (`datetime_kind`), `adapters/introspection.py:46,64`, `views/dynamic/base.py:378`, `core/discovery.py:42`, `core/introspection.py:95` |
| Full **`FieldInfo`** (widget, default, required) | `views/forms.py:600,607,838,858,971`, `views/dynamic/relations.py:61`, `views/dynamic/base.py:226,428,439`, `views/dynamic/inline.py:62`, `core/fields.py:104` (`_find_field_name` identity match), `core/sensitive.py:88` |
| **Instance** fields | `views/dynamic/relations.py:273` (`instance.model_fields`) |
| **`model_validate`** | `views/forms.py:737,978`, `adapters/sqlalchemy.py:145` |
| **`model_dump`** on ORM rows | `views/dynamic/detail.py:39`, `views/static.py:136`, `views/dynamic/inline.py:259`, `views/forms.py:887` |

## Goals

- Every page (list, search, sort, filter, detail, create, edit, delete, inline, relation widgets)
  renders and round-trips for plain SQLAlchemy 2.0 models with single-column primary keys.
- One seam answers "what are this model's fields", with no per-view ORM branching. Every listed call
  site goes through it.
- SQLModel behaviour is byte-for-byte unchanged, and the existing suite passes untouched.
- `core/` stays ORM-free (CONSTITUTION §1–2). SQLAlchemy-specific code lives in `adapters/`.
- A regression guard stops new direct `.model_fields` reads on admin models.
- Polar dogfood (#703) re-run: list, create, detail and edit return 200 for every single-PK model.

## Non-Goals

- Composite primary keys. They stay list-only, as today.
- Rendering relationships as their own form fields. FK columns stay the relation entry point, as
  for SQLModel (`classify_field` → mapper inspection).
- Editable hybrid properties or `column_property`. They are excluded from the schema; showing them
  read-only in `list_display` is a follow-up.
- Imperative or classical mapping (`registry.map_imperatively`) and Core-only `Table` metadata
  (SkyPilot, #714). Both are follow-ups.
- Auto-discovery of plain SQLAlchemy models (#716). It will consume this seam but is specced there.
- Validating SQLModel `table=True` models more strictly than SQLModel itself does.

## BDD Scenarios

```
Scenario: list page renders for a plain SQLAlchemy model
  Given a DeclarativeBase model "Org" with columns id, name, created_at and 3 rows
  When  the admin list page for "org" is requested
  Then  the response is 200 and shows 3 rows with name and created_at columns

Scenario: create form renders one field per mapped column
  Given a DeclarativeBase model with columns id (autoincrement PK), name (String, NOT NULL),
        note (String, nullable), status (Enum), payload (JSON), org_id (FK)
  When  the create form is requested
  Then  it renders name (required), note (optional), status (select of enum values),
        payload (textarea) and org_id (relation select), and no id field

Scenario: create submits, coerces and saves
  Given the model above
  When  the create form is posted with valid values
  Then  a row is inserted with each value coerced to its column type
  And   the response redirects to the list page

Scenario: create rejects invalid input with field errors
  Given the model above
  When  the create form is posted without name and with status="bogus"
  Then  no row is inserted
  And   the form re-renders with errors on name and status

Scenario: edit round-trips and keeps the primary key immutable
  Given an existing row
  When  the edit form is posted with a changed name and a different id
  Then  only name changes

Scenario: detail page shows column values, masking sensitive ones
  Given a model with columns name and api_token
  When  the detail page is requested
  Then  name is shown and api_token is masked, exactly as for SQLModel

Scenario: Mapped annotations win over column python types
  Given a column declared  status: Mapped[Status] = mapped_column(StringEnum(Status))
        where StringEnum is a TypeDecorator over String
  When  the schema is built
  Then  the status field's annotation is Status, so it renders as an enum select

Scenario: columns with no resolvable Python type degrade to Any
  Given a column of a custom TypeDecorator whose python_type raises NotImplementedError
        and no Mapped[...] annotation
  When  the schema is built
  Then  the field's annotation is Any, it renders as a text input, and no exception is raised

Scenario: SQLModel models are unaffected
  Given a SQLModel table model
  When  schema_for(model) is called
  Then  the model class itself is returned

Scenario: regression guard
  Given the source tree
  When  the guard test scans src/hyperadmin for ".model_fields" reads on admin models
  Then  only core/schema.py, adapters/schema.py, adapters/sqlmodel.py and allow-listed
        Pydantic-only sites (settings, action forms) contain them
```

## Design

### Architecture

A new **schema model** concept: for every admin model, a Pydantic `BaseModel` class that describes its
editable column fields.

- SQLModel / Pydantic model → the model class itself (identity, zero cost).
- Plain SQLAlchemy mapped class → a `pydantic.create_model(...)` class generated from the mapper,
  cached per model class.

Call sites ask `schema_for(model)` instead of touching the model. Because the result is a real
Pydantic class, the existing code (`.model_fields`, `.model_validate`, `FieldInfo` handling in
`classify_field` and forms) keeps working unchanged.

```
views/ ──► core/schema.py ◄── adapters/schema.py (registers the SQLAlchemy builder at import)
              │                      │
              │ schema_for(model)    │ build_sqlalchemy_schema(model) → type[BaseModel]
              │ dump_instance(obj)   │ (reads sqlalchemy.inspect(model) — ORM code stays here)
              ▼
     identity for BaseModel subclasses
```

- **`core/schema.py`** (new, ORM-free): `SchemaRegistry`, `schema_registry`, `schema_for()`,
  `dump_instance()`. Holds `(predicate, builder)` pairs. Adapters register builders, so `core/` never
  imports `adapters/` (CONSTITUTION §2).
- **`adapters/schema.py`** (new): `build_sqlalchemy_schema(model)` plus the predicate
  `is_sqlalchemy_mapped(model)`. Registered in `adapters/__init__.py` next to the adapter
  registrations.
- **`adapters/sqlalchemy.py`**: `create()` builds the row as `self.model(**data)` when the model is
  not a Pydantic class. Data arrives already validated by the form via the schema.
- **Call-site migration** (mechanical): `getattr(model, "model_fields", {})` / `model.model_fields`
  → `schema_for(model).model_fields`, and `self.model.model_validate` →
  `schema_for(self.model).model_validate`. `item.model_dump(...)` on ORM rows becomes
  `dump_instance(item, ...)`.

### Building the schema (`adapters/schema.py`)

For each `ColumnProperty` in `inspect(model).column_attrs` that maps exactly one `Column`:

| Aspect | Rule |
|---|---|
| Name / order | Attribute key, in mapper order (declaration order, base classes first, matching SQLModel's `model_fields` order) |
| Annotation | 1. the `Mapped[X]` annotation from `typing.get_type_hints(model, include_extras=False)`, unwrapped. 2. otherwise `column.type.python_type` (`TypeDecorator` → `impl`). 3. otherwise `Any` (`NotImplementedError`) |
| Nullable | `column.nullable` → wrap as `X \| None` if not already optional |
| Default | scalar `column.default.arg` → `default=`. Callable default → `default_factory=` (wrapped to drop SQLAlchemy's context arg), so `is_auto_now_factory` keeps working. `server_default`, `autoincrement` integer PK, or nullable → `default=None`. Otherwise required (`...`) |
| Auto-now hint | `server_default` or `onupdate` present → `json_schema_extra={"sa_column_kwargs": {...}}`, so `forms._is_auto_now_field` needs no change |
| Length | `String(length)` → `max_length` constraint |
| Sensitive | Untouched. `core/sensitive.py` already inspects ORM columns by name |

Excluded: relationships (FK columns stand in for them), `hybrid_property`, `column_property` over
SQL expressions, composite/synonym attributes, deferred `column_property` with multiple columns,
and deferred columns (`mapped_column(..., deferred=True)`, e.g. Polar's `TSVECTOR` search vectors):
they are not loaded with the row, so reading them after the session closes raises
`DetachedInstanceError` (found in the Polar re-run, #703).

The generated class is `create_model(f"{model.__name__}Schema", __config__=ConfigDict(from_attributes=True, arbitrary_types_allowed=True), **fields)`.
It is cached in a `WeakKeyDictionary` keyed by model class, so a test that re-declares a model doesn't
leak.

`FieldInfo` identity matters. `core/fields._find_field_name` matches by identity, so every caller must
get the same cached class. `classify_field(field_info, model_cls)` keeps receiving the **ORM** class as
`model_cls`, so mapper-based FK/M2M detection is unchanged.

### Data Model Changes

No data model changes.

### API / Protocol Changes

New, in `hyperadmin.core.schema`:

```python
SchemaBuilder = Callable[[type], type[BaseModel]]

class SchemaRegistry:
    def register(self, predicate: Callable[[type], bool], builder: SchemaBuilder) -> None: ...
    def schema_for(self, model: type) -> type[BaseModel]: ...

schema_registry: SchemaRegistry

def schema_for(model: type) -> type[BaseModel]:
    """BaseModel subclasses → themselves; else the first matching builder (cached).
    Raises TypeError if no builder matches."""

def dump_instance(instance: object, *, exclude: set[str] | None = None,
                  exclude_none: bool = False) -> dict[str, Any]:
    """BaseModel → model_dump(...); else read schema_for(type(instance)).model_fields
    attributes off the instance (no validation, no lazy relationship loads)."""
```

`SchemaRegistry` and `schema_for` are re-exported from `hyperadmin.core` so third-party adapters can
register builders (CONSTITUTION §5: no `core/` change needed for a new ORM).

Changed behaviour: `SQLAlchemyAdapter.create(data)` builds `self.model(**data)` for non-Pydantic
models. The signature is unchanged.

### Configuration Changes

No configuration changes.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Column type with no `python_type` and no `Mapped[...]` | Annotation `Any`; renders as a text input; debug log naming model and column |
| `get_type_hints` fails (forward ref to an unimported class) | Fall back to `__annotations__` per base, then to `python_type`; never raises |
| `Mapped[Optional[X]]` with `nullable=False` (or the reverse) | `column.nullable` decides optionality; annotation unwrapped then re-wrapped |
| Enum stored via `TypeDecorator` (Polar `StringEnum`) | Resolved through the `Mapped[Enum]` annotation → enum select |
| `JSON` / `JSONB` | `dict \| list \| Any` from `python_type` → existing JSON/textarea widget |
| `Uuid`, `TIMESTAMP(timezone=True)` | `uuid.UUID`, `datetime`; `datetime_kind` still uses column inspection |
| Single-table-inheritance subclass | Schema built per subclass from its mapper; discriminator column excluded from the create form when the mapper sets `polymorphic_identity` |
| Joined-table inheritance | Columns from both tables via mapper `column_attrs`; shared PK not editable |
| Column key ≠ attribute name (`mapped_column("db_name")`) | Attribute key is the field name everywhere |
| Model is neither Pydantic nor mapped | `schema_for` raises `TypeError` with the model name. Today registration already fails earlier with `AdapterNotFoundError` |
| Callable default needing SQLAlchemy context (`ctx`) | Not used as `default_factory`; field becomes optional with `default=None` and the DB/ORM fills it |
| Model mutated after schema built (tests) | `WeakKeyDictionary` cache plus `schema_registry.clear_cache()` for test fixtures |

## Migration & Backward Compatibility

Backward compatible, no migration required.

- SQLModel models: `schema_for` returns the class itself, so every migrated call site computes exactly
  what it did before. The existing suite is the guard.
- Plain SQLAlchemy models: they move from "crashes" to "works". No working behaviour changes.
- New public names (`schema_for`, `SchemaRegistry`, `schema_registry`) are additive. They need an
  integration test before merge (CONSTITUTION §5) and a minor-version changelog entry.

## Implementation Plan

Sub-issues are blocked by `review(spec)`.

| Phase | Scope | Size |
|---|---|---|
| P0 | `review(spec): approve SDD` — human gate | — |
| P1 | `core/schema.py` registry, `schema_for`, `dump_instance` + unit tests (identity for SQLModel, builder dispatch, cache, `TypeError`) | S |
| P2 | `adapters/schema.py` builder + registration + unit tests per row of the "Building the schema" and "Edge cases" tables | M |
| P3 | Migrate all inventory call sites; `SQLAlchemyAdapter.create`; regression-guard test | M |
| P4 | Plain-SQLAlchemy end-to-end unit tests (ASGI client: every BDD scenario) + one Playwright smoke test on an `examples/` plain-SQLAlchemy model + Polar dogfood re-run, results posted on #703 | M |

P3 is a pure mechanical diff with no behaviour change for SQLModel, so it can land after P1 and P2
with the suite as proof.

## Open Questions

- [x] **Public surface:** re-export `schema_for` / `SchemaRegistry` from `hyperadmin.core`.
      Resolved: yes, and `schema_registry` too, so third-party adapters can register builders.
- [x] **Example app for P4:** a new `examples/sqlalchemy/` app (#730), not a section of
      `examples/full-demo`.
- [x] **Read-only computed attributes:** hybrids and `column_property` stay out of scope here
      (follow-up #731).

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Generate a real Pydantic class per SQLAlchemy model | Every consumer already speaks `FieldInfo` / `model_validate`; the call-site diff stays mechanical and SQLModel behaviour stays identical | (a) A new HyperAdmin `FieldSpec` type, with all consumers rewritten: large diff, duplicates Pydantic. (b) `ModelAdmin`-level hand-written schemas: pushes the work onto users |
| Function keyed on model class, not a `BaseAdapter` method | Many sites only hold a model class with no adapter instance: inline models, relation targets, option validation, filters, sensitivity | `BaseAdapter.fields()`: needs adapter instances everywhere; inline/relation targets may be unregistered |
| Registry in `core/`, builder in `adapters/` | Keeps `core/` ORM-free and import direction inward (CONSTITUTION §1–2, §5) | Builder in `core/fields.py`: puts SQLAlchemy mapper code in `core/` (violation) |
| `Mapped[...]` annotation before `python_type` | Preserves enums and precise types behind `TypeDecorator`s (Polar `StringEnum`) | `python_type` only: loses enums, raises on many custom types |
| Columns only, relationships excluded | Matches SQLModel `model_fields`; relation widgets already come from FK columns + mapper inspection | Synthesising relationship fields: diverges from SQLModel and doubles relation handling |
| Regression guard as a source-scanning unit test | Cheap and explicit; stops the assumption creeping back | A ruff custom rule: no plugin infra for that today |
| Re-export `schema_for`, `SchemaRegistry`, `schema_registry` from `hyperadmin.core` | Third-party adapters need the registry to plug in without a `core/` change (CONSTITUTION §5) | Keep internal until a third-party adapter asks |
| P4 example is a new `examples/sqlalchemy/` app (#730) | Keeps the plain-SQLAlchemy demo isolated from the SQLModel full demo and its hotspot files | A section inside `examples/full-demo` |
| Hybrids and `column_property` out of scope (#731) | Read-only computed attributes are a separate display concern; columns-only keeps this change small | Include them as read-only fields now |
