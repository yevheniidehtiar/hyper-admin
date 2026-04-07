---
type: epic
id: PFtDf4Pyy04h
title: "epic: Filter & Choice Scalability (FK preload threshold, filter cache)"
status: todo
priority: medium
owner: null
labels:
  - area:core
  - area:views
  - performance
milestone_ref:
  id: y5aWINuIPslG
github:
  issue_number: 213
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:5d360a47ad0211eef3eaa959b60f5dd7c2fcc63680b9348672cd27c8842e9893
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:38:11Z
updated_at: 2026-03-27T00:46:42Z
---

## Overview
Parent epic for FK widget and filter metadata optimizations.

## Sub-issues

### C1: Smart FK preload threshold
- #236 test: unit tests for smart preload threshold
- #237 feat(core): add preload_threshold to AdminOptions
- #238 feat(adapters): add estimate_row_count() to BaseAdapter
- #239 feat(views): pass preload_threshold to _build_relation_widgets

### C2: Filter metadata caching
- #240 test: unit tests for filter metadata caching
- #241 feat(core): add TTL cache to build_filter_metadata()
- #242 feat(views): use cached filter metadata in list_view

## Bottlenecks addressed
- FK `preload=True` default loads ALL related records as `<option>` tags — browser crash on large tables
- Filter metadata loads `page_size=1000` for every FK field per request with no caching
