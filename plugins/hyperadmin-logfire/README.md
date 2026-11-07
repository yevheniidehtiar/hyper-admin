# hyperadmin-logfire

First-party HyperAdmin plugin that sends admin traces to [Pydantic Logfire](https://logfire.pydantic.dev).

This package is the foundation scaffold: it registers the `logfire` plugin and nothing else yet.
`instrument_admin(admin)` (HTTP and SQL spans) and the adapter, validation and auth events follow.
See `docs/specs/plugin-logfire.md` for the full design.

Disable it with `disabled_plugins=["logfire"]`.
