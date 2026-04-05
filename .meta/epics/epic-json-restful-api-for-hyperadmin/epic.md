---
type: epic
id: y5VW2cjEfD85
title: "Epic: JSON RESTful API for HyperAdmin"
status: todo
priority: medium
owner: null
labels:
  - backend
milestone_ref:
  id: 6DAs1x8ZaPlq
github:
  issue_number: 76
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:440f20f9c1a8d4058a7cc5eb9370aa92fb71fb22a604f76a938a0d4778d020cf
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-10T17:47:36Z
updated_at: 2026-03-28T20:56:23Z
---

## Epic: JSON REST API

Part of milestone: **v0.3.0 — JSON REST API**

### Goal
Expose all HyperAdmin-registered models through a machine-readable RESTful JSON API, auto-generated alongside the existing HTML admin — with auth, pagination, and full OpenAPI docs.

### Dependency Chain

```
JsonApiAdapter protocol (core/adapters.py)
  └─ JsonApiRouter CRUD endpoints (views/json_api.py)
       ├─ Auth integration (session + bearer token)
       ├─ OpenAPI schema enhancements
       └─ Integration tests
            └─ JSON API documentation page
```

### Sub-issues (all to be created)
- [ ] `feat(core)`: `JsonApiAdapter` protocol + response envelope schema
- [ ] `test`: unit tests for protocol shape and pagination meta
- [ ] `feat(views)`: `JsonApiRouter` generating 5 CRUD endpoints per model
- [ ] `feat(views)`: auth integration (session cookie + optional bearer token)
- [ ] `test`: integration tests for all CRUD endpoints with permission checks
- [ ] `docs`: JSON REST API usage guide with curl examples
