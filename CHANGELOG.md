# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **HyperAdmin design system: brand palette, fonts and tokens** (docs/design/system).
  - New palette: HyperAdmin teal (`#0d9488` brand, `#0f766e` actions) and a
    violet "hyper" accent replace the borrowed FastAPI teal and Pydantic coral.
    Every text pair meets WCAG 2.2 AA in light and dark; ratios are listed per
    token in `docs/design/system/tokens.json`.
  - `_tokens.css` / `_dark-mode.css` carry the new values. All existing token
    names still work; new tokens add surfaces (overlay, hover, selected),
    `--ha-color-border-strong`, `--ha-color-focus-ring`, on-colours, chart
    colours, density sizes and z-index layers. Six names that partials used
    without a definition (`--ha-color-bg-subtle`, `--ha-color-muted`,
    `--ha-color-fg-muted`, `--ha-color-success-bg`, `--ha-color-danger-bg`,
    `--ha-color-danger-subtle`) are now defined.
  - Inter and JetBrains Mono are self-hosted as WOFF2 (`static/fonts`,
    `_fonts.css`); logo, favicon and the Lucide icon subset are in
    `static/img` and `static/icons`.
  - Component specs with live previews: open `docs/design/system/index.html`.

### Security
- **Authorization and row scoping on every item handler** (st-v058-byoa-10).
  - Inline cell edit/save, inline add-row, update form, file delete/upload and
    single actions now enforce the model permission and, where an object is
    loaded, the object permission (`change`, or `action_<name>` for actions).
  - `ModelAdmin.get_queryset` row scoping is request-scoped (held in a
    `ContextVar`, not on the shared adapter) and applies to every item, bulk,
    inline and choices handler. Rows hidden from the user return 404, and
    concurrent requests can no longer see each other's filters.
  - `DELETE /{model}/{id}/file/{field}` only accepts file fields and never
    removes a file outside the storage root (absolute paths, `..` and symlinks
    are refused). Uploads also require a file field.
  - Inline formsets reject a submitted child pk that is not an existing child of
    the parent being saved (404, nothing written), and enforce the inline
    model's own `add` / `change` / `delete` permissions when that model is
    registered. An unregistered inline model has no permission rows, so the
    parent's `add` / `change` permission governs its rows.
  - Related rows need `view` on the target model wherever they are disclosed:
    the choices endpoint (403), list-page relation filters (omitted) and the
    create/edit relation widgets (only the selected key is kept, labelled
    `Model (pk)`). An unregistered target falls back to the source model's
    permission.
  - `POST /{model}/upload/{field}` ignores the client path: it stores the
    sanitised basename under a fresh random prefix, never overwrites an
    existing file, refuses names outside the storage root, and returns the
    stored name relative to the storage root (not an absolute server path).
  - Upgrade note for adapter authors: an adapter that implements
    `save_inline_rows` must also implement `inline_child_pks(spec, parent_pk)`.
    The default returns an empty set, so every save of a parent with existing
    inline rows is rejected (404) until it is implemented. See
    `docs/api/adapters.md`.
- **Query oracles on secret columns closed** (st-v058-byoa-53). A user who could
  list a model could previously probe a column such as `password_hash` one
  query at a time. All four oracles are closed:
  - **Filters:** URL `filter_<field>` parameters are honoured only for fields in
    `list_filter`; anything else is ignored.
  - **Search:** inferred search fields (and the adapters' fallback search, and
    the choices `q` search) skip sensitive fields, including fields made
    sensitive only through `AdminOptions.sensitive_fields` on the model's (or
    the choices target's) admin. An explicit `search_fields=[]` passed to an
    adapter now disables search instead of falling back to every text column.
  - **Sort:** `sort_by` is whitelisted against the displayed, non-sensitive
    columns. An unknown value falls back to the default sort (200, never 500).
  - **Choices:** `/{model}/choices/{field}` forwards only the cascade keys the
    relation widget declares (`dependent_on`, `dependent_fields`,
    `relation_filters`) and applies the target admin's `get_queryset`.
  - **Relation labels:** FK filter dropdowns, relation widgets, the choices
    endpoint, popup-create labels and list cells label related rows with the
    model's own `__str__` when it defines one, otherwise with the first
    non-sensitive of `name`, `title`, `label`, `username`, `email`, otherwise
    `Model (pk)`. SQLModel's default `__str__`, which prints every column
    (password hashes included), is never used.
  - **Writes:** a submitted FK value must be a row that the target admin's
    `get_queryset` exposes; otherwise the form is re-rendered with a field
    error (422) and nothing is written.
  - New `hyperadmin.core.sensitive`: a field is sensitive when it carries the
    `hyperadmin_sensitive` marker, or when it is a text (`str` / `bytes`) field
    whose name matches `(^|_)(password|secret|token|hash)(_|$)`;
    `AdminOptions.sensitive_fields` overrides this either way. With SQLModel,
    mark a field with
    `Field(schema_extra={"json_schema_extra": {"hyperadmin_sensitive": True}})`
    (SQLModel's `Field()` rejects a direct `json_schema_extra=` argument); with
    plain Pydantic use `Field(json_schema_extra={"hyperadmin_sensitive": True})`.
    Sensitive fields are hidden from the detail page and inferred list columns.
    Sensitive text fields are write-only on forms and inline rows (an empty
    submission keeps the stored value). A sensitive non-text field (a marked
    boolean or enum) is left out of the edit form and keeps its stored value.
    The built-in `User.password_hash` is marked.
  - Upgrade note: a text column such as `secret_name` now counts as sensitive.
    Opt it back in with `AdminOptions(sensitive_fields={"secret_name": False})`.
    The name heuristic does not apply to booleans, numbers or enums
    (`is_secret: bool`, `token_count: int`).

### Added
- Initial project scaffold
