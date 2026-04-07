---
type: story
id: SLjorwRc_dQD
title: "feat(auth): implement admin login page, session management, and password hashing"
status: done
priority: medium
assignee: null
labels:
  - jules
estimate: null
epic_ref: null
github:
  issue_number: 119
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:dd2b3b8ffac08f0c59ea0613c1482d0ab147e97a143a3a249611c5454a9d314a
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2025-09-21T16:48:34Z
updated_at: 2026-03-20T15:26:00Z
---

## Context

HyperAdmin has no authentication layer yet. All admin routes are publicly accessible. This issue implements the login/logout flow as the foundation for Phase 3 auth (`src/hyperadmin/auth/`).

A `User` model skeleton already exists in `examples/rbac_app/models.py` but lacks a `password_hash` field. No password hashing or session library is currently declared in `pyproject.toml`.

## Acceptance Criteria

- [ ] A `password_hash: str` field is added to the `User` model in `examples/rbac_app/models.py`
- [ ] Password hashing uses `argon2-cffi` (add as runtime dependency in `pyproject.toml`)
- [ ] Starlette `SessionMiddleware` is configured in `examples/rbac_app/main.py` (secret key via env var)
- [ ] `GET /admin/login` renders a login form (new template `src/hyperadmin/templates/auth/login.html`)
- [ ] `POST /admin/login` authenticates the user, creates a session, and redirects to `/admin/`
- [ ] Failed login renders the login form with a generic error message (no user enumeration)
- [ ] `GET /admin/logout` clears the session and redirects to `/admin/login`
- [ ] Auth routes are added to `src/hyperadmin/routing.py` via a dedicated `create_auth_router()` function
- [ ] Auth logic lives in `src/hyperadmin/auth/` — `backend.py` for hashing/verification, `middleware.py` for session dependency

## Implementation Notes

**New files:**
- `src/hyperadmin/auth/__init__.py`
- `src/hyperadmin/auth/backend.py` — `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`
- `src/hyperadmin/auth/middleware.py` — `get_current_user(request: Request, session: AsyncSession) -> User` FastAPI dependency
- `src/hyperadmin/templates/auth/login.html` — extends `base.html`, uses `data-testid="login-form"`

**Modified files:**
- `examples/rbac_app/models.py` — add `password_hash: str = Field(default="", exclude=True)` to `User`
- `examples/rbac_app/create_sample_data.py` — hash passwords during seeding
- `src/hyperadmin/routing.py` — mount auth router before CRUD routes
- `pyproject.toml` — add `argon2-cffi>=23.1` to `[project.dependencies]`

**Dependency direction (CONSTITUTION.md):** `views/` and `routing.py` may import `auth/`; `auth/` must NOT import from `views/` or `adapters/`.

## Testing Requirements

**Unit tests** (`tests/unit/test_auth.py`):
- `hash_password` returns a hash different from the plain text
- `verify_password` returns `True` for correct password, `False` for wrong
- `verify_password` returns `False` for empty plain text

**E2E tests** (`tests/e2e/auth/test_login.py`):
- Unauthenticated request to `/admin/` redirects to `/admin/login`
- Successful login with seeded credentials redirects to `/admin/`
- Failed login shows error message (use `page.get_by_role("alert")`)
- Logout clears session and redirects to login

**E2E selector convention:** use `page.get_by_role()` / `page.get_by_label()` / `page.get_by_test_id("login-form")` — never CSS class selectors.
