---
type: story
id: 66xVdZI5mjPR
title: "test(e2e): login → view protected model → logout flow"
status: done
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - area:auth
  - size:M
estimate: null
epic_ref: null
github:
  issue_number: 362
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9eeeca8471978c5f392ba3b48e682a628a350149267e076565931c635932c1e6
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T08:42:58Z
updated_at: 2026-03-31T16:54:33Z
---

## Context

Playwright E2E test covering the full authentication lifecycle. Validates that middleware, login/logout views, and permission checks work end-to-end under a real browser + HTTP server.

## Scenarios

**Scenario: unauthenticated request is redirected to login**
  Given the admin has `auth_backend` configured
  And   no session cookie is present
  When  GET `/admin/` is requested
  Then  the response is a 302 redirect to `/admin/login`

**Scenario: valid credentials grant session and redirect to dashboard**
  Given a superuser `alice` exists with password `secret123`
  When  POST `/admin/login` with `username=alice&password=secret123`
  Then  the session contains `user_id = alice.id`
  And   the response is a 302 redirect to `/admin/`

**Scenario: invalid credentials re-render login with error**
  Given a superuser `alice` exists with password `secret123`
  When  POST `/admin/login` with `username=alice&password=wrong`
  Then  the login page is re-rendered
  And   an error message "Invalid username or password." is visible
  And   no session is created

**Scenario: authenticated user can view a protected model list**
  Given `alice` is logged in as superuser
  When  GET `/admin/user` is requested
  Then  the response is 200 OK
  And   the list view for User is rendered

**Scenario: auth models visible in sidebar after auto-registration**
  Given `alice` is logged in as superuser
  When  viewing the admin dashboard
  Then  the sidebar contains "Users", "Groups", and "Permissions"

**Scenario: logout clears session and redirects to login**
  Given `alice` is logged in
  When  POST `/admin/logout` is requested
  Then  the session is cleared
  And   the response is a 302 redirect to `/admin/login`

**Scenario: post-logout access is redirected to login**
  Given `alice` has just logged out
  When  GET `/admin/` is requested
  Then  the response is a 302 redirect to `/admin/login`

## Acceptance criteria

- [ ] New file: `tests/e2e/test_auth_flow.py`
- [ ] Auth-enabled app fixture in `tests/e2e/conftest.py` with seeded superuser
- [ ] Each scenario maps to one Playwright test function
- [ ] Inline `# Given / # When / # Then` comments in each test
- [ ] Accessibility-first selectors (`get_by_role`, `get_by_label`, `get_by_text`, `get_by_test_id`)

## Files likely affected

- `tests/e2e/test_auth_flow.py` (new)
- `tests/e2e/conftest.py` (add auth-enabled fixture)

## Dependencies

Depends on: #361

## Notes for implementer

Use sync `Session` + `create_engine` for superuser seeding (same pattern as `createsuperuser` CLI). Follow E2E Selector Convention from CLAUDE.md. Do NOT use `ha-*` CSS classes in selectors.
