# Migrating to HyperAdmin

These guides are for teams that already run an admin built with another Python framework. Each
one has a concept mapping table, a small admin ported step by step with the code before and
after, the authentication and permission mapping, and a list of what HyperAdmin does not have
yet.

| Coming from | What changes | Guide |
|---|---|---|
| Django admin | The web framework, the ORM (Django ORM to SQLModel or SQLAlchemy), the admin classes and the auth. The database can stay | [Migrating from Django admin](from-django-admin.md) |
| SQLAdmin | The admin classes and the authentication backend. Models and database stay | [Migrating from SQLAdmin](from-sqladmin.md) |
| Flask-Admin | The web framework, the model base class, the admin classes and access control. Tables and data stay | [Migrating from Flask-Admin](from-flask-admin.md) |

## What every migration has in common

- **HyperAdmin mounts on a FastAPI app.** `Admin(app, engine=engine)` followed by
  `admin.mount("/admin")`. See [Getting Started](../getting-started.md).
- **The engine is async.** Use an async driver such as `aiosqlite` or `asyncpg`. An app that
  writes with a sync engine can give the admin an async engine on the same database; see
  [Compatibility & Performance](../compatibility.md).
- **Models are SQLModel or SQLAlchemy 2.0 classes**, registered with `site.register(Model)`.
- **HyperAdmin does not change your schema** unless you turn `create_tables` on. Your migrations
  stay in charge.
- **Authentication is either built in or your own.** Built-in auth has its own user, group and
  permission tables. `ExternalAuth` reuses the users, login and permission rules of your app; see
  [Bring Your Own Auth](../guides/external-auth.md).

Every HyperAdmin code sample in these guides has been run end to end. The code for the other
frameworks shows the starting point; their own documentation is the reference for it.

HyperAdmin follows semantic versioning from 1.0.0. Read the
[Versioning & Deprecation Policy](../versioning.md) before you plan a production migration.
