---
type: milestone
id: v058-byoa-01
title: "v0.5.8 — Bring Your Own App (dogfood-1)"
status: todo
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

**Roadmap position 1/16 (2026-09-28 re-cut).** NEW, top priority. Adoption is gated on one thing: can HyperAdmin be added to an *existing* FastAPI app in 10 minutes without taking it over?

Today the admin assumes it owns the app: routes use `{item_id:int}` so UUID/
string primary keys break, `Admin` can run `SQLModel.metadata.create_all`
against the host database, and auth assumes HyperAdmin's own `User` model.
This milestone makes HyperAdmin a guest in someone else's app:

- **Your models** — plain SQLAlchemy 2.0 `DeclarativeBase` and SQLModel models, registered as-is.
- **Your keys** — UUID / string / composite-safe primary keys end-to-end.
- **Your migrations** — the admin never issues DDL against the host DB; Alembic stays yours.
- **Your auth** — map the host app's existing user/session/dependency to admin permissions.
- **Your engine** — reuse the host app's `AsyncEngine` / sessionmaker; no second pool.

Dogfood-1: the milestone closes only after the admin is mounted on a real
existing application and every gap found is fixed or filed.

Epic: `epic-v058-bring-your-own-app`.
