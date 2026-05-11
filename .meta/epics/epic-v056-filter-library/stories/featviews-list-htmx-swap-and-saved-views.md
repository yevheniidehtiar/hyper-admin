---
type: story
id: st-v056-fl-02
title: "feat(views): HTMX tbody swap, saved-view endpoints, SavedView table"
status: todo
priority: high
assignee: null
labels:
  - size:L
  - planned
  - backend
  - upstream-readiness
  - H12
estimate: null
epic_ref:
  id: ep-v056-fl-01
created_at: 2026-05-11T00:00:00Z
updated_at: 2026-05-11T00:00:00Z
---

## Summary

Wire filters into `list_view`. When the request is HTMX, return only the
`<tbody>` fragment and emit `HX-Push-Url` so the URL stays in sync with the
filter state. Add the `SavedView` SQLModel + Alembic migration, plus three
saved-view endpoints scoped to the current user.

**Spec:** [`docs/specs/filter-library.md`](../../../../docs/specs/filter-library.md)

## Files to Change

- **Modified:** `src/hyperadmin/views/dynamic.py` — `list_view` filter pipeline + HTMX swap + saved-view endpoints
- **New:** `src/hyperadmin/filters/saved_views.py` — `SavedView` SQLModel + service
- **New:** `migrations/versions/{rev}_add_hyperadmin_saved_view.py` — Alembic forward-only
- **Modified:** `src/hyperadmin/core/options.py` — `saved_views_enabled: bool = True`
- **Modified:** `tests/unit/test_dynamic_views.py` — list-view filter + saved-view coverage

## Scenarios

```
Scenario: HTMX list request returns tbody fragment with HX-Push-Url
  Given DateRangeFilter and request HX-Request: true
  When  GET /admin/orders/?created_at__gte=2026-01-01
  Then  response body starts with "<tbody"
  And   HX-Push-Url header is "/admin/orders/?created_at__gte=2026-01-01"

Scenario: POST /saved-views creates a row for the current user
  Given alice is authenticated
  When  POST /admin/orders/saved-views with name="Late this month" and querystring="?status=late"
  Then  a SavedView row exists with (user_id=alice.id, model="order", name="Late this month")

Scenario: GET /saved-views returns only the user's own rows
  Given alice has 2 saved views and bob has 1
  When  bob requests GET /admin/orders/saved-views
  Then  the response contains only bob's row

Scenario: DELETE /saved-views/{id} fails for non-owner
  Given alice has saved view id=42
  When  bob issues DELETE /admin/orders/saved-views/42
  Then  response is 404

Scenario: CurrentPeriodDefault redirects on first load
  Given CurrentPeriodDefault(field="created_at", period="month") and no querystring
  When  GET /admin/orders/
  Then  response includes HX-Push-Url with ?created_at__gte=<first of month>&created_at__lte=<today>
```

## Acceptance Criteria

- [ ] Filter pipeline applies all configured filters in order
- [ ] HTMX request → `<tbody>` fragment + `HX-Push-Url`
- [ ] Non-HTMX request → full page render
- [ ] `SavedView` table created via Alembic migration
- [ ] Three saved-view endpoints (list/create/delete) scoped to `request.user.id`
- [ ] DB unique constraint `(user_id, model, name)`
- [ ] `CurrentPeriodDefault` redirect on first load implemented
- [ ] Unit tests for all five scenarios
- [ ] `poe lint` and `poe test:unit` pass

## Blocked by

- `featfilters-add-package-with-six-filters`

## Parent

- Epic: `epic-v056-filter-library`
