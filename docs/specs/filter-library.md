# SDD: Filter Library with Saved Views

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Approved |
| Issue | TBD |
| Milestone | v0.5.6 — Detail Panels & Filter Library |
| Created | 2026-05-11 |
| Last updated | 2026-10-20 |
| Approved by | Yevhenii Dehtiar |
| Approved on | 2026-10-20 |

---

## Problem

`AdminOptions.list_filter` (`src/hyperadmin/core/options.py:75`) accepts a flat
`list[str]` of field names. The renderer compiles each into a typed, whitelisted
`FilterCondition` (`core/filtering.py`, v0.5.8) rendered as a generic exact-match
`<select>` or range input. Real admin work requires richer filter kinds — date ranges,
multi-FK, multi-choice, booleans, "rows owned by me", and "current period"
defaults — plus URL-shareable state and per-user named saved views. Today,
consumers fork the list view to add any of this.

## Goals

- New `src/hyperadmin/filters/` module with six built-in filters:
  `DateRangeFilter`, `MultiFKFilter`, `MultiChoiceFilter`, `BooleanFilter`,
  `IsOwnerFilter`, `CurrentPeriodDefault`.
- `AdminOptions.list_filter` accepts `list[FilterDef | str]` — strings keep the
  legacy auto-classification path; explicit `FilterDef` instances drive the
  new behaviour.
- Filter sidebar rendered as a Jinja partial; submitting it triggers an HTMX
  request that swaps just the table body.
- All filter state lives in the querystring — URLs are shareable, the back
  button works, and refresh preserves state.
- Per-user named saved views persisted in `hyperadmin_saved_view` (the only
  new table). A user can save the current filter set under a name, list their
  saved views, and load one with a single click.
- Permission-aware: `IsOwnerFilter` reuses `ObjectPermissionChecker` from
  v0.5.1 so it honours object-level rules.
- One filter pipeline: every `FilterDef` compiles down to the typed
  `FilterCondition` list that v0.5.8 introduced (`core/filtering.py`), so the
  adapters keep a single whitelisted path from querystring to SQL.

## Non-Goals

- Cross-model filters. Each filter operates on one field/relationship of the
  current model.
- Shared (cross-user) saved views. v0.5.6 saves per-user only.
- Filter expression builder / `OR` / nested groups. The sidebar applies
  filters as `AND`. A boolean expression UI is a later milestone.
- Server-side full-text search over multi-column. That's `search_fields`.

## BDD Scenarios

```
Scenario: legacy string list_filter still classifies fields
  Given AdminOptions(list_filter=["status", "supplier_id"])
  When  the list view renders
  Then  the sidebar renders auto-classified filters for those two fields

Scenario: explicit DateRangeFilter renders two date inputs
  Given AdminOptions(list_filter=[DateRangeFilter(field="created_at")])
  When  the user opens /admin/orders/
  Then  the sidebar exposes inputs created_at__gte and created_at__lte
  And   each input has data-testid="filter-created_at-gte" / "-lte"

Scenario: applying a filter swaps only the table body
  Given the same DateRangeFilter
  When  the user submits created_at__gte=2026-01-01
  Then  an HTMX GET /admin/orders/?created_at__gte=2026-01-01 is issued
  And   the response is a fragment containing only the new <tbody>
  And   the URL is updated via HX-Push-Url

Scenario: IsOwnerFilter restricts to objects the user owns
  Given IsOwnerFilter(owner_fields="created_by") and the user is alice
  When  the user toggles "Mine only" and submits
  Then  the request includes ?is_owner=1
  And   the result rows all have created_by == alice's user key

Scenario: CurrentPeriodDefault preselects the current month on first load
  Given CurrentPeriodDefault(field="created_at", period="month") and no querystring
  When  the user opens /admin/orders/
  Then  the URL is redirected (HX-Push-Url) to ?created_at__gte=<first of month>&created_at__lte=<today>

Scenario: saving the current filter set creates a SavedView row
  Given the user has filters applied
  When  the user posts /admin/orders/saved-views with name="Late this month"
  Then  a hyperadmin_saved_view row exists with (user_id=alice, model="order", name="Late this month", querystring=...)
  And   the sidebar shows "Late this month" as a clickable view

Scenario: loading a saved view applies its querystring
  Given alice has a saved view "Late this month"
  When  alice clicks the saved view
  Then  the list view is requested with that view's querystring
  And   the resulting table body matches the saved filter

Scenario: another user does not see alice's saved views
  Given alice has a saved view "Late this month" and bob is logged in
  When  bob opens /admin/orders/
  Then  the saved-views panel does not list "Late this month"
```

## Design

### Architecture

```
core/options.py            — list_filter type widens to list[FilterDef | str]
core/filtering.py          — existing (v0.5.8): FilterCondition, parse_filter_params;
                             every FilterDef compiles down to it
core/filters_compat.py     — NEW: adapter that wraps legacy strings into FilterDef
filters/                   — NEW package
  __init__.py              — re-export public filter classes
  base.py                  — FilterDef protocol/ABC, render hook, querystring parse hook, apply hook
  date.py                  — DateRangeFilter, CurrentPeriodDefault
  relation.py              — MultiFKFilter
  choice.py                — MultiChoiceFilter
  boolean.py               — BooleanFilter, IsOwnerFilter
  saved_views.py           — SavedView model + service
views/dynamic.py           — list_view passes filter sidebar context; saved-views endpoints
routing.py                 — registers the saved-views routes on the admin router
templates/components/      — filter_sidebar.html, saved_views.html
templates/list.html        — sidebar slot
```

The dependency direction is strict: `filters/` imports from `core/auth.py`
(for `IsOwnerFilter`) but `core/` never imports `filters/`. The adapter
`core/filters_compat.py` is the only seam: it knows how to turn a legacy
string into a concrete `FilterDef` instance from `filters/`.

### Data Model Changes

New SQLModel table:

```python
class SavedView(SQLModel, table=True):
    __tablename__ = "hyperadmin_saved_view"
    id: int | None = Field(default=None, primary_key=True)
    user_key: str = Field(index=True, max_length=255)
    model: str = Field(index=True, max_length=255)
    name: str = Field(max_length=255)
    querystring: str = Field()
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
```

`user_key` is the stringified `request.state.user_key` that the v0.5.8 auth
pipeline sets in both modes (`User.id` with built-in auth, `ExternalAuth.user_key`
in bridge mode), so saved views work for host users too. Timestamps use
`core/timezones.utc_now` and the `UTCNaiveDateTime` type, like the auth models.

HyperAdmin ships no migration tool (BYOA SDD C): the table joins the
`hyperadmin_*` metadata, so `hyperadmin init-db` (or the opt-in DDL step)
creates it on fresh databases, and hosts that run Alembic pick it up through
`hyperadmin.auth.metadata()`-style target metadata. Existing deployments are
unaffected until they add the table.

### API / Protocol Changes

**`FilterDef` protocol** (in `filters/base.py`):

```python
class FilterDef(Protocol):
    field: str                                           # column this filter binds to
    @property
    def slug(self) -> str: ...                           # urlsafe key, defaults to field
    def render(self, ctx: FilterRenderContext) -> str: ...
    def parse(self, qs: MultiDict[str, str]) -> dict[str, Any]: ...
    def compile(self, parsed: dict[str, Any]) -> list[FilterCondition]: ...
```

`compile` returns `FilterCondition` objects (`core/filtering.py`); the adapters
already turn those into SQL (`adapters/_filter_clause.build_clause`), so a
filter never touches the query object and the v0.5.8 whitelist still applies.

**New view methods on `DynamicModelView`** (saved views):

```python
GET    {prefix}/{model}/saved-views          → list current user's saved views (JSON or HTML)   name: {model}-saved-views
POST   {prefix}/{model}/saved-views          → create with name + current querystring          name: {model}-saved-view-create
DELETE {prefix}/{model}/saved-views/{id}     → delete one (must belong to current user)        name: {model}-saved-view-delete
```

The routes are registered in `routing.py` on the admin router, so they run
under `HyperAdminRoute` inside the isolated sub-app: the auth bridge resolves
the user, and the CSRF guard (BYOA SDD D.1) checks POST and DELETE — HTMX
sends the `X-CSRF-Token` header through the `hx-headers` global the base
layout already sets. Templates build the URLs with `url_for`
(`hyperadmin:{model}-saved-views` in isolated mode).

Permission check on every endpoint: only the owning user can read/write their
saved views. Superusers can list everyone's only if `AdminOptions.saved_views_shared = True` (defaults to False — v0.5.6 is per-user).

### Configuration Changes

- `AdminOptions.list_filter` widened to `list[FilterDef | str] | None` (backward compatible).
- `AdminOptions.saved_views_enabled: bool = True`.
- No new env vars.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Legacy string references unknown field | unchanged from today: classifier raises at registration |
| `DateRangeFilter` invalid date input | filter parse returns empty dict; sidebar re-renders with inline `data-testid="filter-{slug}-error"` |
| `MultiFKFilter` choice points to deleted row | classifier rebuilds choices on every list render; stale querystring values are filtered out silently |
| `IsOwnerFilter` with anonymous user | parsing yields `is_owner=False`; filter applies nothing (no leak) |
| `CurrentPeriodDefault` already overridden by user querystring | default is skipped — explicit user input wins |
| Saved view name collision per user | uniqueness enforced via DB unique `(user_key, model, name)` |
| User loads another user's saved-view id | 404 — endpoint scopes to `request.state.user_key` |
| Host mounted under a `root_path` | `HX-Push-Url` and the `CurrentPeriodDefault` redirect use the per-request admin path (`admin_base_path`, BYOA SDD C.1), never the static prefix |
| HTMX request without filters | full list is returned (no filters applied), URL unchanged |
| Non-HTMX request | full page rendered (sidebar + table) |
| Filter applied via HX-Push-Url then user refreshes | querystring fully reconstructs the result |

## Migration & Backward Compatibility

- `list_filter` type widened; old `list[str]` configs keep working.
- New table `hyperadmin_saved_view`, created by `hyperadmin init-db` / the
  opt-in DDL step on fresh databases; existing deployments add it with their
  own migration tool.
- `AdminOptions.saved_views_enabled` defaults True; consumers who don't create
  the table must set it False to avoid 500s on the new endpoints — documented
  in the upgrade guide.
- No `__init__.py` removals; only additions (`hyperadmin.filters.*` re-exports).

## Open Questions

All open questions resolved at approval (2026-10-20):

- [x] `IsOwnerFilter(owner_fields: list[str] | str)` accepts one or several
  owner fields (e.g. `created_by` *or* `assigned_to`); a single field stays the
  common case.
- [x] `CurrentPeriodDefault` redirects with `HX-Push-Url` on first load, so the
  URL is always the source of truth.
- [x] The saved-views sidebar is rendered with the page (no HTMX load): small
  payload, no extra round-trip on every list view.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Filters as a separate top-level package | Boundary kept clean from `core/`; consumers can import filter primitives directly | Stash filters under `core/filters/` (couples core to a richer surface) |
| All state in querystring | Matches Django admin convention; URLs are shareable; back/refresh stay correct | Server-side session-scoped filters (breaks deep links) |
| Per-user saved views in v0.5.6 | Smallest scope that satisfies the H12 acceptance check | Cross-user shared views (out of scope; opens permission model questions) |
| HTMX swap of `<tbody>` (not full list) | Filter sidebar stays stable, mobile keeps scroll position | OOB swap of full list (more bytes; flashes the sidebar) |
| Legacy `list[str]` retained | Avoids a breaking change in `AdminOptions` | Force migration to `FilterDef` (semver-major) |
| `IsOwnerFilter(owner_fields=...)` accepts one or many fields (approved) | "Mine" often means created *or* assigned; a list costs nothing for the single-field case | Single `owner_field` only (consumers subclass for the OR case) |
| `CurrentPeriodDefault` redirects with `HX-Push-Url` (approved) | Querystring stays the single source of truth; refresh and share links behave the same as a manual filter | Emit hidden inputs on first load (URL lies about the applied filter) |
| Saved-views sidebar rendered with the page (approved) | A few rows per user; one request instead of two per list view | HTMX-load the sidebar (extra round-trip, flashes on every navigation) |
| `FilterDef.compile` returns `FilterCondition` lists (alignment with v0.5.8) | Adapters already consume `FilterCondition`; keeps the typed whitelist as the only path to SQL | `apply(query)` hook that mutates the adapter query (bypasses the whitelist) |
| Saved views keyed by `request.state.user_key` (alignment with v0.5.8) | Works for host users in `ExternalAuth` bridge mode, where there is no `hyperadmin_user` row | Integer `user_id` FK to the built-in user table (breaks bridge mode) |
