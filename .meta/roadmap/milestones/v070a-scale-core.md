---
type: milestone
id: y5aWINuIPslG
title: "v0.7.0a — Scale Core"
target_date: 2026-08-31T00:00:00Z
status: in_progress
github:
  milestone_id: 8
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:ac67c36b4641dce8719729f9010250714a846d6b56d60b520d485193677dbeb8
  synced_at: 2026-04-07T17:23:23.788Z
created_at: 2026-03-27T00:32:17Z
updated_at: 2026-09-28T00:00:00Z
---

**Roadmap position 3/16 (2026-09-28 re-cut).** Scale-core is the subset every real app hits in week one: N+1-free relation loading (A1 selectinload), configurable `search_fields` in both adapters (A2), COUNT caching (A3), and filter/choice scalability (FK preload threshold + filter-metadata TTL cache). Epics #211 (A1–A3) and #213. Keyset pagination, pool tuning/rate limiting and the E2E scalability suite moved to v0.7.0b.

Original scope (before the 2026-09-28 split): Address 8 critical bottlenecks for 10M+ records, 100 req/s, 100 tables with 5+ relations. Epics: Adapter Query Performance, Engine & Connection Management, Filter & Choice Scalability, E2E Validation.
