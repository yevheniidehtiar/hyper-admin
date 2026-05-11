---
type: story
id: st-v056-fl-01
title: "feat(filters): new package with six built-in filters and FilterDef protocol"
status: todo
priority: high
assignee: null
labels:
  - size:M
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

Add the `src/hyperadmin/filters/` package with `FilterDef` protocol and six
concrete filters. Widen `AdminOptions.list_filter` to `list[FilterDef | str]`
and add a compat shim that wraps legacy strings into a generic exact-match
`FilterDef`.

**Spec:** [`docs/specs/filter-library.md`](../../../../docs/specs/filter-library.md)

## Files to Change

- **New:** `src/hyperadmin/filters/__init__.py`
- **New:** `src/hyperadmin/filters/base.py` — `FilterDef`, `FilterRenderContext`
- **New:** `src/hyperadmin/filters/date.py` — `DateRangeFilter`, `CurrentPeriodDefault`
- **New:** `src/hyperadmin/filters/relation.py` — `MultiFKFilter`
- **New:** `src/hyperadmin/filters/choice.py` — `MultiChoiceFilter`
- **New:** `src/hyperadmin/filters/boolean.py` — `BooleanFilter`, `IsOwnerFilter`
- **New:** `src/hyperadmin/core/filters_compat.py` — legacy `str → FilterDef` adapter
- **Modified:** `src/hyperadmin/core/options.py` — widen `list_filter` type
- **New:** `tests/unit/test_filters.py`

## Scenarios

```
Scenario: legacy list_filter=["status"] is wrapped into a FilterDef
  Given AdminOptions(list_filter=["status"])
  When  the list view collects filters
  Then  filters[0] is an instance of FilterDef
  And   filters[0].field == "status"

Scenario: DateRangeFilter.parse extracts gte/lte from querystring
  Given DateRangeFilter(field="created_at")
  When  parse({"created_at__gte": "2026-01-01", "created_at__lte": "2026-01-31"}) is called
  Then  the result is {"gte": date(2026,1,1), "lte": date(2026,1,31)}

Scenario: IsOwnerFilter with anonymous user applies nothing
  Given IsOwnerFilter(owner_field="created_by") and request.user is None
  When  apply(query, parsed={"is_owner": True}) is called
  Then  the query is returned unchanged
```

## Acceptance Criteria

- [ ] Six filter classes implemented per SDD signatures
- [ ] `FilterDef` protocol with `render`, `parse`, `apply` hooks
- [ ] Legacy `str` entries wrapped via `core/filters_compat.py`
- [ ] `AdminOptions.list_filter` widened (backward compatible)
- [ ] Unit tests cover all three scenarios + per-filter parse/apply behaviour
- [ ] `poe lint` passes

## Blocked by

- `reviewspec-approve-sdd-filter-library`

## Parent

- Epic: `epic-v056-filter-library`
