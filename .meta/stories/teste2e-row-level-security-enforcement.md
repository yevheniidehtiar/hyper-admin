---
type: story
id: DoAjgyxybD52
title: "test(e2e): row-level security enforcement"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 432
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8b3e6c8bbd2fb5198814002a58dd23a27a7048cd2c8ca1856bb85bb3fbee7db1
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-04-01T21:38:37Z
updated_at: 2026-04-01T21:38:37Z
---

## Context

End-to-end Playwright tests verifying that object-level permissions and row-level query filtering work correctly through the full stack (browser -> view -> adapter -> database).

## Scenarios

**Scenario: user A cannot view user B's record**
  Given user A owns record #1, user B owns record #2
  And   `ObjectPermissionChecker` checks ownership
  When  user A navigates to record #2 detail
  Then  a 403 page is shown

**Scenario: user A sees only their own records in list view**
  Given user A owns 2 records, user B owns 3 records
  And   `get_queryset` filters by `owner_id`
  When  user A views the list
  Then  only 2 records are displayed

**Scenario: user A cannot delete user B's record**
  Given user A owns record #1, user B owns record #2
  When  user A attempts to delete record #2
  Then  a 403 response is returned

## Acceptance Criteria

- [ ] E2E test app with two users and ownership-based permissions
- [ ] All 3 scenarios pass as Playwright tests
- [ ] Inline `# Given / # When / # Then` comments in each test
- [ ] Uses accessibility-first selectors per E2E selector convention

## Files Likely Affected
- `tests/e2e/test_object_permissions.py` (new)
- `tests/e2e/conftest.py` (fixture updates for multi-user setup)

## Dependencies
Depends on: #430 (all OLP view wiring complete)

## Notes for Implementer
- Follow E2E patterns in `tests/e2e/test_auth_flow.py`
- Need a test app with a model that has `owner_id` field
- Use `page.get_by_role()`, `page.get_by_text()` — no `.ha-*` selectors
