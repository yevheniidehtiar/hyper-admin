---
type: epic
id: bz_SWmq9yUG6
title: "epic: Adapter Query Performance (selectinload, pagination, count, search)"
status: todo
priority: medium
owner: null
labels:
  - area:core
  - area:adapters
  - performance
milestone_ref:
  id: r5QTaoU0QKpG
github:
  issue_number: 211
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b4b729b660d93b2a6e7584cb09e53c4fe387ef5aaa76ccded09fcb763499ae5e
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:37:38Z
updated_at: 2026-03-27T00:46:38Z
---

## Overview
Parent epic for adapter-level query optimizations addressing 4 critical scalability bottlenecks.

## Sub-issues

### A1: Configurable relationship loading
- #215 test: unit tests for configurable selectinload
- #216 feat(core): add load_relations parameter to BaseAdapter
- #217 feat(adapters): implement configurable selectinload
- #218 feat(views): wire list_select_related/detail_select_related

### A2: Configurable search fields
- #219 test: unit tests for configurable search_fields
- #220 feat(core): add search_fields to AdminOptions
- #221 feat(adapters): implement configurable search_fields
- #222 feat(views): pass search_fields to adapter

### A3: COUNT query optimization
- #223 test: unit tests for count caching
- #224 feat(core): add count caching protocol
- #225 feat(adapters): implement count caching with TTL

### A4: Keyset (cursor) pagination
- #226 test: unit tests for keyset pagination
- #227 feat(core): extend BaseAdapter with cursor params
- #228 feat(adapters): implement keyset pagination
- #229 feat(views): wire keyset pagination into list_view
- #230 feat(templates): update pagination for cursor mode

## Bottlenecks addressed
- Unconditional `selectinload` on ALL relations (5+ extra SELECTs per list request)
- OFFSET-based pagination degrades linearly (OFFSET 10M scans 10M rows)
- COUNT(*) on every request with no caching (seconds on 10M rows)
- ILIKE `%search%` on unindexed columns (full table scan)
