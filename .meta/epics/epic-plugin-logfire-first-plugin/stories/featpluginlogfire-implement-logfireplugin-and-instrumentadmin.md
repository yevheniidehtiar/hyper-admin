---
type: story
id: xbcCPwi1Ikew
title: "feat(plugin-logfire): implement LogfirePlugin and instrument_admin()"
status: todo
priority: high
assignee: null
labels:
  - backend
  - size:M
  - planned
  - plugins
  - observability
estimate: null
epic_ref:
  id: Plo-enMpTWhB
created_at: 2026-05-05T00:00:00Z
updated_at: 2026-05-05T00:00:00Z
---

## Summary

Implement the core `LogfirePlugin` class and the `instrument_admin(admin)`
public function. `instrument_admin` is the user's one-call setup; `LogfirePlugin`
is the entry-point class that the registry discovers automatically.

**Spec:** [`docs/specs/plugin-logfire.md`](../../../../docs/specs/plugin-logfire.md)

## Files to Change

- **Modified:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/plugin.py`
- **Modified:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/__init__.py`
- **New:** `plugins/hyperadmin-logfire/src/hyperadmin_logfire/_config_check.py`

## Design

```python
# plugin.py
import logging
import logfire

log = logging.getLogger("hyperadmin_logfire")

class LogfirePlugin:
    name = "logfire"

    def on_register(self, admin) -> None:
        # No instrumentation here — that happens in instrument_admin().
        # on_register is just confirmation that the plugin loaded.
        log.info("hyperadmin-logfire plugin registered (call instrument_admin to enable)")
```

```python
# __init__.py
from ._config_check import is_logfire_configured, warn_if_not_configured
from .plugin import LogfirePlugin
import logfire

def instrument_admin(admin) -> None:
    """One-call setup. Idempotent.

    1. Verify the plugin is loaded (not disabled).
    2. logfire.instrument_fastapi(admin.app)
    3. logfire.instrument_sqlalchemy(admin.engine)
    """
    if "logfire" not in admin.plugins:
        log.warning(
            "instrument_admin called but the logfire plugin is disabled "
            "or not installed; HTTP/SQL instrumentation skipped"
        )
        return
    warn_if_not_configured()  # one-shot WARNING if logfire.configure() not called
    logfire.instrument_fastapi(admin.app)
    logfire.instrument_sqlalchemy(engine=admin.engine)
```

```python
# _config_check.py
_warned = False

def is_logfire_configured() -> bool:
    # heuristic: logfire's get_baggage / current span APIs all rely on a global
    # tracer provider being installed; check that. Concrete API call to be
    # picked at implementation time after consulting logfire docs.
    ...

def warn_if_not_configured() -> None:
    global _warned
    if _warned or is_logfire_configured():
        return
    _warned = True
    log.warning(
        "hyperadmin-logfire requires logfire.configure() to be called before "
        "instrument_admin(); no spans or events will be emitted"
    )
```

## Scenarios

**Scenario: instrument_admin attaches the plugin and emits adapter spans**
  Given logfire is configured to capture spans in a test sink
  And   instrument_admin(admin) has been called
  When  the admin.products list view is requested
  Then  the test sink contains a span named "admin.adapter.list" with attribute model="Product"

**Scenario: plugin no-ops when logfire is not configured**
  Given logfire.configure() was NOT called
  When  Admin is constructed and a list view is requested
  Then  no exceptions are raised
  And   a single warning log mentions hyperadmin-logfire requires logfire.configure()

**Scenario: instrument_admin is a no-op when plugin is disabled**
  Given Admin(disabled_plugins=["logfire"]) is constructed
  When  instrument_admin(admin) is called
  Then  no logfire.instrument_fastapi / instrument_sqlalchemy is called
  And   a WARNING log is emitted

## Acceptance Criteria

- [ ] `LogfirePlugin` discoverable via entry point (proven by `hyperadmin plugins list`)
- [ ] `instrument_admin(admin)` calls `logfire.instrument_fastapi` and `instrument_sqlalchemy`
- [ ] One-shot warning on missing `logfire.configure()`
- [ ] No-op when plugin is disabled
- [ ] Idempotent: calling `instrument_admin` twice doesn't double-instrument
  (defer to logfire's idempotency)

## Blocked by

- `chore-scaffold-pluginshyperadmin-logfire-package`
- Epic 1: `featcore-wire-plugin-discovery-into-admin-init` (so plugin is discoverable)
- Epic 1: `featcore-implement-app-level-hook-dispatcher` (so dispatch exists)

## Parent

- Epic: `epic-plugin-logfire-first-plugin`
