# SDD: Bulk Actions with Parameter Forms

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.5.5 — Bulk Actions & Autocomplete |
| Created | 2026-05-10 |
| Last updated | 2026-05-10 |

---

## Problem

HyperAdmin's `@action` decorator (`src/hyperadmin/core/actions.py`) and
`run_action` view (`src/hyperadmin/views/dynamic.py`) currently support only
single-record actions invoked from a detail page. `ActionDef.requires_selection`
exists as reserved metadata but is not wired anywhere. Consumer admins
routinely need to:

1. Apply an action to many selected rows in a list view (the H3 upstream check).
2. Collect parameters before running the action (reason note, deadline,
   destination warehouse) via a server-rendered form.
3. See a per-row outcome page when some rows succeed and others fail, so the
   operator can retry only the failures.

Without these, every consumer reinvents bulk operations as ad-hoc list-view
buttons that bypass the admin's permission and audit machinery.

## Goals

- A `@action` decorator that opts into bulk mode (`bulk=True`) and an optional
  parameter form (`form=PydanticModel`).
- A list-view checkbox column + action selector + "Run" button that POSTs to a
  new bulk endpoint.
- A confirmation/param-collection page rendered when `form` is set, before the
  action runs.
- A per-row result page summarising success/failure for each selected row, with
  a follow-up "retry failures" affordance.
- `requires_selection=True` is enforced — clicking Run with no rows selected
  re-renders the list with an inline warning.
- Permission re-check per row inside the bulk handler (selection does not
  bypass `_check_object_permission`).

## Non-Goals

- Async / background-job execution. v0.5.5 runs the bulk action in-request; a
  later milestone can introduce a job-runner adapter.
- Cross-model bulk actions. An action is bound to one `ModelAdmin`.
- Streaming progress updates over WebSocket. The result page is rendered once,
  after all rows are processed.
- Configurable concurrency / batch size. Rows are processed sequentially.

## BDD Scenarios

```
Scenario: bulk action with no selection re-renders list with warning
  Given a ModelAdmin with @action(label="Archive", bulk=True, requires_selection=True)
  When  the user clicks "Run" on the list view with no rows checked
  Then  the list re-renders with a flash "Select at least one row"
  And   the handler is not invoked

Scenario: bulk action with param form prompts before running
  Given a ModelAdmin with @action(label="Reassign", bulk=True, form=ReassignParams)
  When  the user selects 3 rows and clicks Run on action "reassign"
  Then  the response renders a Pydantic-derived form at /admin/orders/actions/reassign/bulk
  And   the form preserves the selected ids in hidden inputs

Scenario: bulk action with valid params runs over selected rows
  Given the same ReassignParams form with field operator: int
  When  the user posts the form with operator=42 and ids=[1,2,3]
  Then  the handler runs three times — one per id — with form data validated
  And   the per-row outcome page lists 3 rows with status "ok"

Scenario: per-row failure is surfaced without aborting the bulk run
  Given the handler raises HTTPException(403) for id=2 only
  When  the user posts the bulk form with ids=[1,2,3]
  Then  the result page shows ok / failed / ok for ids 1, 2, 3 respectively
  And   the failed row carries the error message "permission denied"
  And   the user sees a "Retry failures" link that re-submits with ids=[2]

Scenario: requires_selection blocks zero-row submission server-side
  Given the user crafts a POST to /admin/orders/actions/archive/bulk with ids=[]
  When  the request reaches the bulk endpoint
  Then  the response is 400 with detail "Selection required"
  And   the handler is not invoked

Scenario: object-level permission is enforced per row
  Given an ObjectPermissionChecker that denies "archive" on id=2
  When  the user posts a bulk archive with ids=[1,2,3]
  Then  the result page shows ok / forbidden / ok
  And   adapter.delete was called for ids 1 and 3 only
```

## Design

### Architecture

Three modules touched:

```
core/actions.py          — extend ActionDef + decorator with bulk/form params
views/dynamic.py         — new bulk endpoint + per-row outcome renderer
templates/components/    — checkbox column, action selector, bulk_form, bulk_result
```

No new top-level module. The bulk endpoint is a sibling of the existing
single-record `run_action` handler.

Request flow:

```
GET  /{model}/                                       → list with checkboxes + action <select>
POST /{model}/actions/{name}/bulk          (no form) → run handler over ids, render result
POST /{model}/actions/{name}/bulk           (form=X) → render param form prefilled with ids
POST /{model}/actions/{name}/bulk/confirm   (form=X) → validate Pydantic form, run, render result
```

The "confirm" suffix only exists for form-bearing actions. Form-less actions
go straight from list submit to result.

### Data Model Changes

No DB tables added. `ActionDef` gains two fields (frozen dataclass replaced with
`@dataclass(frozen=True, slots=True, kw_only=True)`):

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ActionDef:
    name: str
    label: str
    handler: Callable[..., Any]
    requires_selection: bool = False
    bulk: bool = False
    form: type[BaseModel] | None = None
```

### API / Protocol Changes

**Decorator:**

```python
@action(
    label: str,
    *,
    requires_selection: bool = False,
    bulk: bool = False,
    form: type[BaseModel] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]
```

Validation at decoration time:
- `form is not None` implies `bulk is True` (raise `TypeError` otherwise).
- `bulk is True` requires the handler signature `(self, request, item_id, *, params=None)`
  where `params` is the validated Pydantic instance (or `None` for form-less actions).
  Validated by inspection of `inspect.signature` at decorator time.

**Endpoints (added to `DynamicModelView`):**

```python
async def run_bulk_action(
    self,
    request: Request,
    action_name: str,
) -> Response: ...

async def confirm_bulk_action(
    self,
    request: Request,
    action_name: str,
) -> Response: ...
```

`run_bulk_action` parses `ids` from the form payload (multi-valued
`ids=1&ids=2&...`), checks `requires_selection`, dispatches to the param-form
renderer or directly to per-row execution.

**Per-row result:**

```python
class BulkRowResult(NamedTuple):
    id: Any
    status: Literal["ok", "failed", "forbidden"]
    detail: str | None
```

Rendered via `templates/components/bulk_result.html` listing each row with its
status and a "Retry failures" link.

### Configuration Changes

`AdminOptions` gains no new fields. List-view checkbox column is rendered when
any registered action has `bulk=True`. If no bulk actions exist, the column is
omitted (zero-cost for admins that don't use it).

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Action not found / not bulk | 404 with message "Bulk action 'x' not found" |
| `ids` missing or empty + `requires_selection=True` | 400 "Selection required" |
| `ids` contains non-existent row | per-row "failed" with detail "row not found" |
| Pydantic form validation error | re-render form with field errors and selected ids preserved |
| Handler raises `HTTPException(403)` | per-row "forbidden" with `detail` from exception |
| Handler raises any other `Exception` | per-row "failed" with `str(exc)`, logged at WARNING |
| Object-permission denied | per-row "forbidden" (same as 403) |
| HTMX request (`hx-request` header) | bulk endpoint returns an HTMX fragment to swap into result region |
| Action handler returns `Response` | ignored in bulk mode — return value reserved for single-record path |

## Migration & Backward Compatibility

Backward compatible. Existing single-record `@action` decorators (no `bulk`,
no `form`) keep working unchanged. The `run_action` endpoint stays. New defaults
are false / `None`. No database migration required.

## Open Questions

- [ ] Should `bulk=True` actions automatically gain `requires_selection=True`? Default proposal: yes, with explicit `requires_selection=False` opt-out for actions that operate on all matching rows (e.g. "Archive all overdue").
- [ ] Should the bulk endpoint accept `select_all_matching_filter=true` as an alternative to explicit ids, so a million-row archive doesn't ship a million ids in the request? Deferred to a follow-up unless the v0.5.5 demo needs it.
- [ ] Should the result page expose a "rollback" affordance when all rows failed? Default: no — the admin's audit log is the rollback surface.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Pydantic for param forms | Already the project's validation surface; reuses existing form rendering machinery | WTForms, hand-rolled dataclass |
| Sequential per-row execution | Simplest; preserves request-scoped transaction semantics in adapters | asyncio.gather with semaphore; bg-job dispatch |
| Per-row outcome page (not abort-on-first-failure) | Operator can retry just the failures; matches H3 acceptance check | All-or-nothing transaction; first-failure abort |
| Bulk endpoint at `/actions/{name}/bulk` (not `/{id}/action/{name}` extended) | Keeps single-record route unchanged; clearer in logs | Overload `run_action` with `ids` query param |
