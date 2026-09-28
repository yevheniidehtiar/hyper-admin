---
type: epic
id: ep-v058-byoa-01
title: "epic(core): Bring Your Own App — mount into an existing FastAPI app without taking over"
status: todo
priority: critical
owner: null
labels:
  - planned
  - area:core
  - dogfood
  - size:L
milestone_ref:
  id: v058-byoa-01
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Overview

Make HyperAdmin the admin you add to an existing FastAPI app in 10 minutes
without it taking over — your models, your UUID keys, your migrations, your
auth. Driven by dogfood-1: mounting the admin on a real, pre-existing
application and fixing every friction point found.

An SDD (`docs/specs/bring-your-own-app.md`) is required before implementation
(touches `core/`, `routing.py`, `views/`, `auth/`).

## Known gaps on develop (verified 2026-09-28)

- `routing.py` registers detail/update/delete/inline/action/file routes with `{item_id:int}` — UUID and string PKs 404.
- `views/forms.py` / `views/dynamic.py` type inline parent/child PKs as `int`.
- `Admin._create_db_and_tables()` runs `SQLModel.metadata.create_all` on the configured engine.
- Auth integration assumes HyperAdmin's own `User`/`Group`/`Permission` models.

## Stories

1. docs(spec): SDD for Bring Your Own App
2. feat(routing): primary-key-agnostic routes (UUID / str / int)
3. feat(core): never run DDL on the host database (opt-in `create_tables` only)
4. feat(adapters): plain SQLAlchemy 2.0 DeclarativeBase models + host engine/sessionmaker reuse
5. feat(auth): bring-your-own-auth adapter (host user → admin permissions)
6. docs+examples: "10-minute BYOA" guide and `examples/byoa/` (Alembic, UUID keys, host auth)
7. chore(dogfood): dogfood-1 on a real existing app — gap log filed as stories

## Acceptance

- [ ] An existing FastAPI app with Alembic migrations, UUID PKs and its own auth mounts the admin with < 20 lines of code
- [ ] No DDL is executed against the host DB unless explicitly requested
- [ ] Full CRUD + inlines + actions + file fields work with UUID primary keys (unit + E2E)
- [ ] The guide is followed start-to-finish in under 10 minutes on a clean checkout
- [ ] Dogfood-1 gap log reviewed; blocking gaps fixed in this milestone
