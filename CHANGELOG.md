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

### Added
- Initial project scaffold
