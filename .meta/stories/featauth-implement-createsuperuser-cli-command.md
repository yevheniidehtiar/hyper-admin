---
type: story
id: uWGAbnyEEHGE
title: "feat(auth): implement createsuperuser CLI command"
status: done
priority: medium
assignee: null
labels:
  - jules
estimate: null
epic_ref: null
github:
  issue_number: 118
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:43dbbfe64795e12852766952039883ae7d66c07fe1c5d5ceea264da00d7886f0
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2025-09-21T16:48:34Z
updated_at: 2026-03-20T10:20:26Z
---

## Context

HyperAdmin has no management commands. Administrators bootstrapping a fresh deployment have no way to create the first superuser without writing a custom script. This issue adds a `createsuperuser` CLI command using Typer (already available via FastAPI's transitive deps, but should be declared explicitly).

**Depends on:** #119 (password hashing via `argon2-cffi` and `User` model with `password_hash`)

## Acceptance Criteria

- [ ] A `createsuperuser` command is available via `python -m hyperadmin createsuperuser` (or `uv run python -m hyperadmin createsuperuser`)
- [ ] The command accepts `--username`, `--email`, and `--password` as CLI options (interactive prompts when omitted)
- [ ] `--password` prompt is a hidden input (no echo); prompts twice for confirmation
- [ ] The command validates: username uniqueness, non-empty email, password length ≥ 8 characters
- [ ] On success: prints a confirmation message and exits with code 0
- [ ] On validation failure: prints a clear error and exits with code 1 (no traceback)
- [ ] On DB error (e.g., duplicate username): prints a user-friendly error and exits with code 1
- [ ] The command uses `argon2-cffi` to hash the password before storing (via `src/hyperadmin/auth/backend.hash_password()`)
- [ ] `typer` is added as an explicit runtime dependency in `pyproject.toml`

## Implementation Notes

**New files:**
- `src/hyperadmin/management/__init__.py`
- `src/hyperadmin/management/commands/createsuperuser.py` — Typer app with `createsuperuser` command
- `src/hyperadmin/__main__.py` — `python -m hyperadmin` entry point that delegates to the management CLI

**Modified files:**
- `pyproject.toml` — add `typer>=0.12` to `[project.dependencies]`; add `[project.scripts] hyperadmin = "hyperadmin.__main__:app"` entry point

**DB session** — the command needs a synchronous SQLAlchemy session (the async engine in `src/hyperadmin/db.py` is for web requests; use `sqlmodel.Session` with a sync engine constructed from the same DB URL, passed via `--database-url` option or `DATABASE_URL` env var).

**Dependency direction (CONSTITUTION.md):** `management/` is a new top-level module; it may import `auth/` and `core/`; `core/` must NOT import from `management/`.

**Example invocation:**
```bash
uv run python -m hyperadmin createsuperuser \
  --username admin \
  --email admin@example.com \
  --password secret1234
```

## Testing Requirements

**Unit tests** (`tests/unit/test_createsuperuser.py`) — use Typer's `CliRunner`:
- Command with valid args creates a user with `is_superuser=True` and hashed password
- Command with duplicate username exits with code 1 and prints an error
- Command with password < 8 chars exits with code 1 with a validation message
- Command with `--password` and mismatched confirmation prompt exits with code 1

**Manual verification:**
```bash
# Start fresh
uv run python -m hyperadmin createsuperuser --username admin --email admin@example.com
# Enter and confirm password interactively
# Then log in at /admin/login with those credentials
```
