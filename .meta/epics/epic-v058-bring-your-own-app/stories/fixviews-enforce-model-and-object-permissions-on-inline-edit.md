---
type: story
id: st-v058-byoa-10
title: "fix(views): enforce permissions and row scoping on item, inline, bulk, file and choices handlers"
status: todo
priority: critical
assignee: null
labels:
  - size:M
  - planned
  - area:views
  - layer:views
  - security
estimate: null
epic_ref:
  id: ep-v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Summary

Close live authorization gaps. This is a bug fix that needs no SDD (Owner decision 4), so it is **not blocked by the SDD gate** and can ship now.

- **Missing model and object checks.**
  - `inline_edit_form_view` and `inline_save_view` skip `_check_permission` and `_check_object_permission`.
  - `inline_add_row_view` has no check at all.
  - `update_form_view` and `delete_file_view` skip the object check.
  - `run_action` never loads the object, never applies the queryset filter and never checks `action_<name>`.
- **Arbitrary file deletion.** `delete_file_view` never checks that `field_name` is a file field. It calls `os.remove` on a path built from any column's value, and `FileSystemStorage.get_path` lets an absolute value escape the storage root. The fix: return 404 unless `field_name` is in `_get_file_fields()`, and resolve every storage path through the new `core/storage_paths.resolve_storage_path`. That helper is shared with `_collect_file_paths` and, later, with `views/uploads.py`. `upload_file_view` also requires a file-field `field_name`.
- **Inline formset IDOR and reparenting.** Submitted `<prefix>-<i>-pk` values are trusted as-is. `save_inline_rows` must load the parent's existing child keys (`WHERE fk_field == parent_pk`) and reject any other pk with a 404, before any write. The inline model's own `add`, `change` and `delete` permissions are enforced. This is fixed in both adapters.
- **Row scoping.** `inline_edit_form_view`, `inline_save_view`, `delete_file_view`, `run_action` and `_execute_bulk` call `adapter.get` outside `_request_queryset_filter`, so `get_queryset` (tenant/RLS scoping) is bypassed.
  - The filter must become request-scoped. It moves from shared adapter-instance state into a `contextvars.ContextVar`.
  - Every item and bulk handler enters the context.
  - The v0.5.3 tenancy amendment depends on this.
- **Choices.** Require `view` on the target model as well as the source model.

**Spec:** [`docs/specs/bring-your-own-app.md`](../../../../docs/specs/bring-your-own-app.md) — sections: B.6, A.3, A.6

## Files to Change

- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/views/forms.py`
- `src/hyperadmin/core/adapters.py` (request-scoped queryset filter via `ContextVar`)
- `src/hyperadmin/core/storage_paths.py` (new)
- `src/hyperadmin/adapters/sqlmodel.py`, `src/hyperadmin/adapters/sqlalchemy.py` (`save_inline_rows` ownership)
- `tests/unit/test_dynamic_authz_gaps.py`

## Scenarios

```
Scenario: inline cell save enforces change permission
  Given the user lacks change_order
  When  POST /admin/order/5/inline/status is sent
  Then  the response is 403
  And   the field is unchanged

Scenario: inline edit form enforces object permission
  Given an object permission checker denies change on order 5
  When  GET /admin/order/5/inline/status/edit is requested
  Then  the response is 403

Scenario: inline add-row requires permission
  Given a user without add_order or change_order
  When  GET /admin/order/inline/lines/add-row is requested
  Then  the response is 403

Scenario: single action enforces object permission
  Given an object permission checker denies action_archive on order 5
  When  the archive action is run on order 5
  Then  the response is 403
  And   the action handler is not called

Scenario: single action respects the queryset filter
  Given get_queryset hides order 5 from the user
  When  the archive action is run on order 5
  Then  the response is 404

Scenario: inline save respects the queryset filter
  Given get_queryset hides order 5 from the user
  When  POST /admin/order/5/inline/status is sent
  Then  the response is 404

Scenario: bulk action respects the queryset filter
  Given get_queryset hides order 5 from the user
  When  the bulk archive action is posted with ids 4 and 5
  Then  order 5 is reported as not found
  And   the action handler is not called for order 5

Scenario: a queryset filter never leaks across concurrent requests
  Given two concurrent requests from tenants A and B
  When  both load the same order id
  Then  each request is filtered by its own tenant

Scenario: deleting a non-file field is refused
  Given an authenticated user with change_order
  When  DELETE /admin/order/5/file/notes is sent
  Then  the response is 404
  And   order 5's notes are unchanged

Scenario: file delete never leaves the storage root
  Given Invoice 1 whose file field pdf holds "/etc/hosts"
  When  DELETE /admin/invoice/1/file/pdf is sent
  Then  no file outside the storage root is removed

Scenario: inline formset rejects another parent's child row
  Given Order 1 with line 10 and Order 2 with line 20
  When  the user saves Order 1 posting lines-0-pk=20
  Then  the response is 404
  And   line 20 still belongs to Order 2 with its original values

Scenario: inline formset cannot delete another parent's child row
  Given Order 2 with line 20
  When  the user saves Order 1 posting lines-0-pk=20 and lines-0-DELETE=on
  Then  line 20 still exists

Scenario: choices require view permission on the target model
  Given a user with view_order but not view_user
  When  GET /admin/order/choices/customer is requested
  Then  the response is 403
```

## Acceptance Criteria

- [ ] Every scenario above has a passing test
- [ ] Every `DynamicModelView` handler that calls the adapter does so inside `_request_queryset_filter` (asserted by a unit test)
- [ ] `delete_file_view`, `_collect_file_paths` and `upload_file_view` go through `resolve_storage_path` and the file-field check
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- None. This is a standalone security fix (Owner decision 4), so it is not gated by `st-v058-byoa-00`.

## Parent

- Epic: `epic-v058-bring-your-own-app` (v0.5.8 — Bring Your Own App)
