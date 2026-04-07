---
type: story
id: Gjw_YwMZKHDr
title: "feat(templates): update pagination component for cursor mode"
status: todo
priority: medium
assignee: null
labels:
  - agent-task
  - area:templates
  - size:S
  - performance
estimate: null
epic_ref:
  id: fkINeqAy7AVG
github:
  issue_number: 230
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:3979b389b2252d1c6e3f2291de93d78be8a5fa4e527ed5bcdb41aa3aedeae3b1
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2026-03-27T00:41:33Z
updated_at: 2026-03-29T18:26:25Z
---

## Context
Part of Epic #211 (A4: Keyset/cursor pagination).

## Acceptance criteria
- [ ] When `pagination_mode="keyset"`, shows prev/next with cursor params instead of page numbers
- [ ] HTMX `hx-get` uses cursor query params
- [ ] When `pagination_mode="offset"` (default), unchanged behavior
- [ ] Accessible: prev/next buttons have proper ARIA labels

## Files
- `src/hyperadmin/templates/components/pagination.html`

## Dependencies
- Blocked by: #229 (A4.4 views wiring)
- Blocking: D1.1
