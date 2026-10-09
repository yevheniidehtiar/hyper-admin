---
type: epic
id: ep-v070b-keyset-01
title: "epic(adapters): keyset (cursor) pagination for 10M+ row lists"
status: todo
priority: medium
owner: null
labels:
  - area:adapters
  - performance
  - scale-advanced
milestone_ref:
  id: v070b-scale-02
created_at: 2026-09-28T00:00:00Z
updated_at: 2026-09-28T00:00:00Z
---

## Overview

Story group **A4** of `docs/specs/adapter-query-performance.md`, split out of
epic #211 (Adapter Query Performance) during the 2026-09-28 roadmap re-cut so
that v0.7.0a (scale-core) ships A1–A3 (selectinload, search_fields, COUNT
cache) without waiting on cursor pagination.

Opt-in `pagination_mode="cursor"` on `AdminOptions`: opaque base64-urlsafe
cursors over `(sort_col, pk)`, `total=None` in cursor mode, graceful fallback
to OFFSET for non-deterministic sorts, 400 on tampered cursors.

**SDD:** [`docs/specs/adapter-query-performance.md`](../../../docs/specs/adapter-query-performance.md) (§A4)

## Stories

- #226 test: unit tests for keyset pagination in adapter
- #227 feat(core): extend BaseAdapter.list() with cursor pagination params
- #228 feat(adapters): implement keyset pagination in SQLModelAdapter
- #229 feat(views): wire keyset pagination into list_view and pagination template
- #230 feat(templates): update pagination component for cursor mode

## Parent

- Milestone: v0.7.0b — Scale Advanced
- Split from: epic #211 (Adapter Query Performance)
