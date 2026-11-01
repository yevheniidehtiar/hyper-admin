---
type: story
id: st-v059-nav-05
title: "feat(nav): opt-in record search in the command palette"
status: backlog
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - backend
  - frontend
estimate: null
epic_ref:
  id: ep-v059-nav-01
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Summary

Follow-up (not specced in detail). Let models opt in with `palette_search=True` so the palette also finds records via their `search_fields`, through one capped endpoint that filters by `view_<model>` and the queryset/object scoping. Needs an SDD addendum first.

**Spec:** [`docs/specs/navigation-and-list-ux.md`](../../../../docs/specs/navigation-and-list-ux.md)

## Files to Change

- `src/hyperadmin/views/` (new endpoint)
- `static/js/palette.js`
- `core/options.py`

## Scenarios

```
Scenario: records of opted-in models appear in the palette
  Given OrderAdmin(palette_search=True) and order "ORD-1042"
  When  the user types "1042" in the palette
  Then  "ORD-1042" is listed under Orders

Scenario: models without opt-in are never queried
  Given CustomerAdmin without palette_search
  When  the user types any query
  Then  no query runs against the customer table
```

## Acceptance Criteria

- [ ] SDD addendum approved (endpoint, caps, debounce, permission filtering)
- [ ] At most N results per model and M models per request; debounced input
- [ ] Unit tests with Scenario docstrings; `uv run poe test:cov-diff` reports 100% of changed lines
- [ ] `uv run ruff check . && uv run ruff format --check .` and `poe lint` pass
- [ ] E2E tests map 1:1 to the scenarios, use role/label/test-id locators only, with `# Given / # When / # Then` comments
- [ ] Visual baselines refreshed on Linux (`RESPONSIVE_SNAPSHOTS_UPDATE=1`) where the UI changed
- [ ] Manual test scenarios attached to the PR
- [ ] New `data-testid`s added to the CLAUDE.md reference table

## Blocked by

- `featnav-cmd-ctrl-k-command-palette-with-recent-items-and-sho` (st-v059-nav-04)

## Parent

- Epic: `epic-v059-navigation`
