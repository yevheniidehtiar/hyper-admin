---
type: epic
id: ixW_WgZMF9Xq
title: "epic(core): Pydantic Settings — Flexible Configuration"
status: done
priority: medium
owner: null
labels:
  - agent-task
  - area:core
  - area:settings
milestone_ref:
  id: WUIXeOSj83Kt
github:
  issue_number: 383
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:743790f151e2d9994aaf2db5db6f311c858c0bf8107dceddc6fbb35666d91375
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-31T09:12:07Z
updated_at: 2026-03-31T19:59:11Z
---

## Overview

Django-like centralized settings via pydantic-settings BaseSettings. All scalar config moves exclusively into `HyperAdminSettings` — no duplicate params on `Admin()`. Replaces hardcoded db.py, secures session secret, provides `.env` file support with `HYPERADMIN_` prefix.

### Before
```python
Admin(app, engine=engine, session_secret="...", theme="dark",
      auto_discover=True, create_tables=True, auth_backend=backend)
```

### After
```python
settings = HyperAdminSettings(secret_key="...", theme="dark")
Admin(app, engine=engine, settings=settings, auth_backend=backend)
# or just: Admin(app, engine=engine)  # loads from env/defaults
```

## Tasks

- [ ] #374 — docs(spec): SDD for Pydantic Settings (human gate)
- [ ] #375 — feat(core): add pydantic-settings dependency and HyperAdminSettings class
- [ ] #376 — feat(core): wire HyperAdminSettings into Admin class
- [ ] #377 — feat(core): replace hardcoded db.py with settings-driven engine
- [ ] #378 — feat(core): secure session_secret — warn on default, require when auth enabled
- [ ] #379 — test: settings loading, validation, env override
- [ ] #380 — docs: update examples to use HyperAdminSettings

## Dependency Graph

```
#374 → #375 ─┬→ #376 ─┬→ #378
              │        ├→ #379
              │        └→ #380
              └→ #377
```

## Parallel Tracks

#374 (SDD review) is a human gate — blocks all implementation.
#375 is the foundation after SDD approval.
#376 and #377 can proceed in parallel after #375.
#378, #379, #380 require #376.
