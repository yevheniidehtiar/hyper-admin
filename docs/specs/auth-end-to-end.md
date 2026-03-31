# SDD: Auth End-to-End Wiring — Remaining Gaps

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | Epic A (v0.3.0) |
| Milestone | v0.3.0 — Zero-Config & Auth |
| Created | 2026-03-30 |
| Last updated | 2026-03-30 |

---

## Problem

The auth stack (middleware, session backend, login/logout views, permission checker, CLI) is
implemented and unit-tested. Two gaps remain:

1. `User`, `Group`, and `Permission` models are not auto-registered in the admin site when
   `auth_backend` is configured. Developers must register them manually, which defeats the
   self-contained nature of the auth module.
2. No E2E Playwright test validates the full login → CRUD access → logout cycle under a real
   browser + HTTP server, leaving the integration untested end-to-end.

## Goals

- Auto-register auth models when `auth_backend` is set, with sensible options (no delete for User,
  filter by `is_active`/`is_superuser`).
- Provide an E2E Playwright fixture and test covering: redirect to login, credential verification,
  CRUD access, and logout.

## Non-Goals

- OAuth2, SSO, or any auth backend other than `SessionAuthBackend`.
- Two-factor authentication.
- Password reset flow.
- Rate limiting / brute-force protection (out of scope for v0.3.0).

## BDD Scenarios

```
Scenario: auth models appear in admin sidebar when auth is enabled
  Given Admin is configured with auth_backend=SessionAuthBackend(engine)
  When  admin.mount("/admin") is called
  Then  site._registry contains User, Group, and Permission models
  And   User is registered with can_delete=False
  And   User list_filter includes is_active and is_superuser

Scenario: unauthenticated request is redirected to login
  Given the admin has auth_backend configured
  And   no session cookie is present
  When  GET /admin/ is requested
  Then  the response is a 302 redirect to /admin/login

Scenario: valid credentials grant session and redirect to dashboard
  Given a superuser alice exists with password "secret123"
  When  POST /admin/login with username=alice&password=secret123
  Then  the session contains user_id = alice.id
  And   the response is a 302 redirect to /admin/

Scenario: invalid credentials re-render login with error
  Given a superuser alice exists with password "secret123"
  When  POST /admin/login with username=alice&password=wrong
  Then  the login page is re-rendered
  And   an error message "Invalid username or password." is visible
  And   no session is created

Scenario: authenticated user can view a protected model list
  Given alice is logged in as superuser
  When  GET /admin/user is requested
  Then  the response is 200 OK
  And   the list view for User is rendered

Scenario: logout clears session and redirects to login
  Given alice is logged in
  When  POST /admin/logout is requested
  Then  the session is cleared
  And   the response is a 302 redirect to /admin/login

Scenario: post-logout access is redirected to login
  Given alice has just logged out
  When  GET /admin/ is requested
  Then  the response is a 302 redirect to /admin/login
```

## Design

### Architecture

Affected modules:
- `core/app.py` — add `_register_auth_models()`, called from `mount()` when `auth_backend` is set
- `tests/e2e/test_auth_flow.py` (new) — Playwright E2E tests
- `tests/e2e/conftest.py` — add auth-enabled app fixture with seeded superuser

No new production modules required. This is wiring, not new logic.

### Data Model Changes

No data model changes. Auth models (`User`, `Group`, `Permission`) already exist.

### API / Protocol Changes

No API changes. New internal method only:

```python
# src/hyperadmin/core/app.py
def _register_auth_models(self) -> None:
    """Register User, Group, Permission in admin when auth is enabled."""
    from hyperadmin.core.registry import site
    from hyperadmin.auth.models import User, Group, Permission
    from hyperadmin.core.options import AdminOptions

    if User not in site._registry:
        site.register(
            User,
            options=AdminOptions(
                can_delete=False,
                list_filter=["is_active", "is_superuser"],
            ),
        )
    if Group not in site._registry:
        site.register(Group)
    if Permission not in site._registry:
        site.register(Permission, options=AdminOptions(can_create=False, can_delete=False))
```

### Configuration Changes

No new parameters. `_register_auth_models()` is called automatically inside `mount()`:

```python
def mount(self, path: str) -> None:
    if self.auth_backend:
        self._register_auth_routes(path)
        self._register_auth_models()   # ← new call
    ...
```

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| User already explicitly registered | Skip — `site.register()` raises `ValueError`; catch and skip |
| auth_backend is None | `_register_auth_models()` not called |
| DB tables not yet created at mount time | Two-phase timing: models are registered at `mount()` time (import/startup), DB tables are created later in the `on_event("startup")` handler. Requests arrive only after both phases complete. Do NOT place model registration inside the startup handler. |
| Superuser fixture in E2E conftest uses sync engine | Use synchronous `Session` + `create_engine` (same pattern as `createsuperuser` CLI) |

## Migration & Backward Compatibility

Backward compatible — no migration required.

Apps that already manually register `User` in admin will see the new auto-registration
silently skip (due to the "already registered" guard). No behavior change for those apps.

## Open Questions

All resolved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| `Permission` registered with `can_create=False, can_delete=False` | Permissions are auto-generated by `PermissionSyncService`; manual CRUD would bypass the sync logic and risk inconsistency | Allow full CRUD; rejected — permissions must stay in sync with registered models |
| E2E fixture seeds superuser with sync engine | `createsuperuser` CLI already uses this pattern; consistency > purity | Async fixture; rejected — adds complexity for a one-time seeding operation |
| Place `_register_auth_models()` call in `mount()` not `__init__()` | `site` registry may have user models registered between `__init__` and `mount()`; checking at mount time avoids double-registration | Call in `__init__`; rejected — too early, may race with explicit registrations |
