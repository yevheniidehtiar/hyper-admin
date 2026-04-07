---
type: story
id: cIUrCn98_zlg
title: "1.4.2.4: Add filter bar and fix list view table overflow"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - frontend
  - jules
estimate: null
epic_ref: null
github:
  issue_number: 106
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:d3ca8572ab66ca2261ebb3488a175e56177b6cf4b7572b990b3f4cd55c96380a
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2025-09-21T16:48:02Z
updated_at: 2026-03-19T21:16:32Z
---

**Issue Title:** 1.4.2.4: Add filter bar to the list view & fix table overflow

**Agent Persona:** Frontend Agent

## Current State

- **Search:** ✅ Already implemented — a free-text search input (`search_input.html`) that searches across string columns via the adapter's `search` parameter.
- **Field-level filtering:** ❌ Not implemented — no UI to filter by specific field values (booleans, relationships, enums, etc.).
- **Table overflow:** 🐛 When models have many columns or on narrow screens, the table extends beyond the main content area. `.ha-table-wrapper` uses `overflow: hidden` which clips content silently instead of providing horizontal scroll.

## What Needs to Be Done

### Part 1: Filter Bar Component

Add a collapsible filter bar above the list table (below search, above the table) that renders field-specific filter controls based on model introspection.

#### Filter control types by field type:

| Field type | Control | Options |
|-----------|---------|---------|
| `bool` | `<select>` dropdown | 3 states: "Any" (default/no filter), "Yes", "No" |
| FK / relationship | `<select>` dropdown | "Any" (default) + all related objects (fetched from DB), displayed via `__str__` |
| `Enum` | `<select>` dropdown | "Any" (default) + all enum members |
| `str` (with limited distinct values) | `<select>` dropdown or skip (use search instead) |
| `int` / `float` / `date` / `datetime` | Range inputs (min/max) — **stretch goal, not required for MVP** |

#### Implementation steps:

1. **`AdminOptions` — add `list_filter` config:**
   - Add `list_filter: list[str] = []` to `AdminOptions` — field names to show in the filter bar.
   - When `list_filter` is non-empty, the filter bar is rendered.

2. **Filter metadata builder** (new utility or method on `DynamicModelView`):
   - For each field in `list_filter`, introspect the model to determine:
     - Field type (bool, FK, enum, etc.)
     - Available choices (enum values, or query related objects for FK fields)
   - Return a list of filter descriptors: `[{name, label, type, choices: [{value, label}]}]`

3. **Wire `filters` dict into `DynamicModelView.list_view()`:**
   - Parse filter query params from the request (e.g., `?filter_is_admin=true&filter_group_id=3`)
   - Build a `filters` dict and pass it to `self.adapter.list(..., filters=filters)`
   - The adapter already supports `filters` — both `SQLAlchemyAdapter` and `SQLModelAdapter` iterate `filters.items()` and apply `column == value`.
   - For bool "Any" state: omit the key from filters entirely.

4. **Filter bar template** (`components/filter_bar.html`):
   - Render a horizontal bar of `<select>` dropdowns, one per `list_filter` field.
   - Each dropdown: label + options (with "Any" as default empty value).
   - Use HTMX: `hx-get` on change → reload `#model-list` with filter params appended to search/sort/pagination params.
   - Preserve current filter values on page reload (populate `selected` from context).

5. **Include filter bar in `list_layout.html`:**
   - Between search input and `#list-container`.
   - Only render if `list_filter` is non-empty.

6. **Pass filter state through pagination/sort/search links:**
   - `pagination.html` and `sortable_header.html` must preserve filter params in their URLs.

#### Acceptance Criteria:
- [ ] `AdminOptions.list_filter` accepts a list of field names
- [ ] Bool fields render as 3-state select (Any / Yes / No)
- [ ] FK/relationship fields render as select with all related objects
- [ ] Filters compose with search, sort, and pagination (all preserved across interactions)
- [ ] HTMX-powered: no full page reload
- [ ] Filter bar only appears when `list_filter` is configured
- [ ] `data-testid="filter-bar"` on the container, `data-testid="filter-{field_name}"` on each select

### Part 2: Fix List View Table Overflow

The `.ha-table-wrapper` in `hyperadmin.css` uses `overflow: hidden` which clips the table silently when there are many columns or on narrow viewports.

**Fix:** Change to `overflow-x: auto` so the table scrolls horizontally when it exceeds the container width.

```css
.ha-table-wrapper {
  overflow-x: auto;
}
```

#### Acceptance Criteria:
- [ ] Table scrolls horizontally on narrow screens instead of overflowing or being clipped
- [ ] No visual regression on normal-width screens with few columns

## Testing

- Unit tests: filter metadata builder returns correct descriptors for bool/FK/enum fields
- Unit tests: `list_view` passes `filters` dict to adapter when filter params present
- E2E tests: filter bar renders, selecting a filter updates the table via HTMX
- E2E tests: table is scrollable horizontally when many columns are present

## Files likely to change

- `src/hyperadmin/core/options.py` — add `list_filter`
- `src/hyperadmin/views/dynamic.py` — parse filter params, build filter metadata, pass to adapter and template
- `src/hyperadmin/templates/components/filter_bar.html` — new component
- `src/hyperadmin/templates/list_layout.html` — include filter bar
- `src/hyperadmin/templates/components/pagination.html` — preserve filter params
- `src/hyperadmin/templates/components/sortable_header.html` — preserve filter params
- `src/hyperadmin/static/css/hyperadmin.css` — fix `overflow: hidden` → `overflow-x: auto`
- `tests/unit/test_list_view.py` — filter tests
- `tests/e2e/test_list_view.py` — filter + overflow tests

## MANDATORY: Pre-Push Verification

Before pushing ANY code, you MUST run these commands and verify they pass with exit code 0:

```bash
uv sync --all-extras
uv run poe lint        # MUST exit 0 — runs ruff check, ruff format, mypy, basedpyright
uv run poe test:unit   # MUST exit 0
```

If `uv run poe lint` fails, fix ALL errors and re-run until clean. Do NOT push code that fails lint. Do NOT skip this step. Do NOT report success without actually running the commands.
