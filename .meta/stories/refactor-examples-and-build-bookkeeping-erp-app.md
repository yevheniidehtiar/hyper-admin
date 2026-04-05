---
type: story
id: Ke_lZSr4ytgD
title: Refactor Examples and Build Bookkeeping ERP App
status: done
priority: medium
assignee: null
labels: []
estimate: null
epic_ref: null
github:
  issue_number: 172
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3d9c77899fe0d2a1adb2d7bc28213d82c10d623d4f67a175488d1da2c7fa9220
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:51:01Z
updated_at: 2026-03-31T20:00:41Z
---

## Epic: Bookkeeping ERP Reference App

Part of milestone: **v0.2.1 — Developer Experience & Examples**

### Goal
Provide a realistic, domain-driven example app that demonstrates HyperAdmin with relational data, custom reports, and multi-module admin discovery — so adopters can onboard quickly.

### Dependency Chain

```
Restructure examples/ (simple/ + remove rbac_app)
  └─ ERP SQLModel models (contacts, sales, purchases, accounting)
       ├─ ERP admin config (auto-discovery per module)
       └─ Faker seeding script
            └─ Annual P&L custom report view
                 └─ ERP README + docs update
```

### Sub-issues
- [x] `chore(examples)`: restructure `examples/` — move simple app, delete rbac_app
- [x] `feat(examples)`: ERP domain models (Contact, Invoice, Bill, Account, JournalEntry...) #192 
- [x] `feat(examples)`: ERP admin config with auto-discovery per module #193
- [x] `feat(examples)`: Faker seeding script (100+ contacts, 500+ invoices, 800+ bills) #194
- [x] `feat(examples)`: Annual P&L custom report view #195
- [x] `docs`: ERP README with run instructions and seed command #196
