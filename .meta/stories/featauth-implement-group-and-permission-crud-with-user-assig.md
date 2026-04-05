---
type: story
id: x16rEcCHjNtX
title: "feat(auth): implement Group and Permission CRUD with user assignment in admin"
status: done
priority: medium
assignee: null
labels:
  - jules
estimate: null
epic_ref: null
github:
  issue_number: 115
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8c02466e0764a0de32e91e9b2bb7a948a34ecf36d621310b7c4c7c6854254122
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-21T16:48:34Z
updated_at: 2026-03-20T15:25:54Z
---

## Context

`Group`, `Permission`, `UserGroup`, and `UserPermissions` models are fully defined in `examples/rbac_app/models.py` but are not yet registered with the admin interface. The many-to-many join tables (`UserGroup`, `UserPermissions`) need inline or separate admin views to support user-to-group and user-to-permission assignments.

**Depends on:** #116 (User model CRUD must be in place before assigning users to groups)

## Acceptance Criteria

**Group admin:**
- [ ] `GroupAdmin(ModelView, model=Group)` defined in `examples/rbac_app/admin.py`
- [ ] `column_list`: `id`, `name`, `description`, `is_active`, `created_at`
- [ ] `column_searchable_list`: `name`
- [ ] `column_sortable_list`: `id`, `name`, `created_at`
- [ ] `column_filters`: `is_active`
- [ ] `form_columns`: `name`, `description`, `is_active`

**Permission admin:**
- [ ] `PermissionAdmin(ModelView, model=Permission)` defined in `examples/rbac_app/admin.py`
- [ ] `column_list`: `id`, `name`, `codename`, `content_type`, `created_at`
- [ ] `column_searchable_list`: `name`, `codename`
- [ ] `column_sortable_list`: `id`, `name`, `codename`
- [ ] `form_columns`: `name`, `codename`, `description`, `content_type`

**User-Group assignment:**
- [ ] `UserGroupAdmin(ModelView, model=UserGroup)` defined in `examples/rbac_app/admin.py`
- [ ] `column_list`: `id`, `user_id`, `group_id`, `joined_at`, `is_active`
- [ ] `form_columns`: `user_id`, `group_id`, `is_active`

**User-Permission assignment:**
- [ ] `UserPermissionsAdmin(ModelView, model=UserPermissions)` defined in `examples/rbac_app/admin.py`
- [ ] `column_list`: `id`, `user_id`, `permission_id`, `granted_at`, `granted_by`, `is_active`
- [ ] `form_columns`: `user_id`, `permission_id`, `granted_by`, `is_active`

**General:**
- [ ] All four admin classes are registered and appear in the sidebar

## Implementation Notes

**Modified files:**
- `examples/rbac_app/admin.py` — add `GroupAdmin`, `PermissionAdmin`, `UserGroupAdmin`, `UserPermissionsAdmin`
- No core library changes needed — standard `ModelView` registration is sufficient

**Relationship fields** — FK fields (`user_id`, `group_id`, `permission_id`) render as integer inputs by default. If `ModelView` supports select widgets for FK fields, use them; otherwise integer inputs are acceptable for this phase.

## Testing Requirements

**Unit tests** (`tests/unit/test_group_permission_admin.py`):
- Groups can be created and retrieved
- Permissions can be created and retrieved
- UserGroup assignment can be created (user-group many-to-many)

**E2E tests** (`tests/e2e/auth/test_group_crud.py`):
- Group list renders at `/admin/group` with `data-testid="list-table"`
- Create group form accessible; fields via `page.get_by_label("Name")`, etc.
- Sidebar shows "Groups" and "Permissions" links (use `page.get_by_role("link", name=...)`)
