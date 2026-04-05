---
type: story
id: jStde5VYBQy8
title: "feat(views): HTMX autocomplete endpoint for async relation choice search"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
estimate: null
epic_ref:
  id: IYTFerusYXD-
github:
  issue_number: 165
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:7c0a8e6742f139f7476f53a2851d7656528312daf48f9ec350f9e3128abfe5f4
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-20T15:37:57Z
updated_at: 2026-03-26T23:50:16Z
---

> **Part of:** #159
> **Depends on: #161, #164**

## Context

Large relation tables (users, products, countries) cannot be preloaded. An HTMX endpoint
must return a filtered `<datalist>` or `<optgroup>` partial based on a search query,
enabling type-ahead autocomplete inside the multiselect widget.

## Acceptance Criteria

- [ ] New endpoint registered in `DynamicModelView`:
  `GET /admin/{model_name}/choices/{field_name}?q=&limit=50&offset=0`
- [ ] Returns an HTML partial (`text/html`) rendering `widgets/choices_options.html` (new template)
  — a `<option>` list fragment, not a full page
- [ ] Calls `adapter.get_choices(field, q=q, limit=limit, offset=offset)`
- [ ] Respects `limit` max 200; returns HTTP 400 for oversized requests
- [ ] Handles missing field gracefully (HTTP 404)
- [ ] Authenticated: uses existing auth middleware (request must be logged in)
- [ ] Unit tests: mock adapter, assert correct HTML fragment and error handling
- [ ] E2E test: type in relation field → dropdown appears with filtered options

## Files Likely Affected

- `src/hyperadmin/views/dynamic.py`
- `src/hyperadmin/routing.py`
- `src/hyperadmin/templates/widgets/choices_options.html` (new)
- `tests/unit/test_dynamic_choices_endpoint.py` (new)
- `tests/e2e/test_relation_select.py` (new)

## Dependencies

Depends on: #161, #164

## Notes for Implementer

Route pattern: `/{model_name}/choices/{field_name}` — register alongside existing CRUD routes.
Content-Type must be `text/html` (HTMX expects HTML fragments).
`hx-swap="innerHTML"` targets the `<select>` inner content, not the wrapper.
