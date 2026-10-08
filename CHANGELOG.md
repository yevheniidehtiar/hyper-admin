# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
    model's own `add` / `change` / `delete` permissions.
  - The choices endpoint requires `view` on the target model as well as the
    source model.
- **Query oracles on secret columns closed** (st-v058-byoa-53). A user who could
  list a model could previously probe a column such as `password_hash` one
  query at a time. All four oracles are closed:
  - **Filters:** URL `filter_<field>` parameters are honoured only for fields in
    `list_filter`; anything else is ignored.
  - **Search:** inferred search fields (and the adapters' fallback search, and
    the choices `q` search) skip sensitive fields.
  - **Sort:** `sort_by` is whitelisted against the displayed, non-sensitive
    columns. An unknown value falls back to the default sort (200, never 500).
  - **Choices:** `/{model}/choices/{field}` forwards only the cascade keys the
    relation widget declares (`dependent_on`, `dependent_fields`,
    `relation_filters`) and applies the target admin's `get_queryset`.
  - New `hyperadmin.core.sensitive`: a field is sensitive when it is marked
    `json_schema_extra={"hyperadmin_sensitive": True}` or its name matches
    `(^|_)(password|secret|token|hash)(_|$)`; `AdminOptions.sensitive_fields`
    overrides this either way. Sensitive fields are hidden from the detail page
    and inferred list columns, and are write-only on forms (an empty submission
    keeps the stored value). The built-in `User.password_hash` is marked.
  - Upgrade note: a column such as `secret_name` or `token_count` now counts as
    sensitive. Opt it back in with `AdminOptions(sensitive_fields={"secret_name": False})`.

### Added
- Initial project scaffold
