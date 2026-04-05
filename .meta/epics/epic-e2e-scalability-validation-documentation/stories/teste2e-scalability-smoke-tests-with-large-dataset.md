---
type: story
id: nIxbVf0heJwE
title: "test(e2e): scalability smoke tests with large dataset"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:tests
  - agent:claude
  - size:L
  - performance
estimate: null
epic_ref:
  id: 0ayKU0p1nvDC
github:
  issue_number: 243
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:e2a0d842692ca8cb2d0183cd9c7c8e3fd56a58bcd59e20b26ed5a8c0eb8427f5
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:44:09Z
updated_at: 2026-03-27T00:44:09Z
---

## Context
Part of Epic #214 (D1: E2E scalability validation).
Validates all scalability improvements work together end-to-end.

## Acceptance criteria
- [ ] Seed 10K+ records across multiple related tables in conftest
- [ ] Test list view loads in <2s with configurable selectinload
- [ ] Test FK select widget doesn't crash browser (lazy HTMX for large FK tables)
- [ ] Test keyset pagination works correctly on deep pages
- [ ] Test search returns results within acceptable time
- [ ] Test filter bar loads quickly (cached metadata)
- [ ] Test offset pagination still works (backward compat)

## Files
- `tests/e2e/test_scalability.py` (new)
- `tests/e2e/conftest.py` (seed fixture)

## Dependencies
- Blocked by: #218 (A1.4), #222 (A2.4), #225 (A3.3), #230 (A4.5), #239 (C1.4), #242 (C2.3)
- Blocking: D1.2
