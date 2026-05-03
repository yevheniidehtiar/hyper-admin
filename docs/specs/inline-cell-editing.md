# SDD: Inline Cell Editing in List View

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft (dispatch-authorized for implementation) |
| Issue | #45 (epic 2.4 — UI/UX Polish, v0.5.0 scope: inline model editing) |
| Milestone | v0.5.0 — Advanced UX |
| Created | 2026-05-03 |
| Last updated | 2026-05-03 |

---

## Problem

The list view currently exposes only a row-level edit affordance (a link that
navigates to a separate update form). For light edits — toggling an
`is_active` flag, fixing a typo in a `name`, bumping a `price` — this round
trip is heavy: page navigation, form render, submit, redirect back to the
list. Django's admin solved this with `list_editable`. HyperAdmin needs the
same affordance, implemented with HTMX so editing happens in place without a
full reload.

This is the last open scope item in milestone v0.5.0 (UI polish, themes,
WCAG, **inline model editing**). The first three are shipped via #72/#73/#74.
The inline-editing piece was scoped but never tracked as a sub-issue.

## Goals

- A `ModelAdmin.list_editable` allow-list controls which fields are editable
  inline. Empty by default — no behaviour change for existing users.
- Editable cells render an explicit edit affordance (button) inside the cell
  in the list view.
- Activating the affordance swaps the cell to an inline editor (input or
  select) via HTMX `hx-get`.
- Saving via HTMX `hx-post` validates server-side using the existing
  `PydanticForm` validators and either re-renders the cell (success, with an
  `aria-live` confirmation) or returns a 422 fragment with field errors.
- Cancelling restores the static cell.
- Keyboard: `Enter` submits, `Escape` cancels, focus is returned to the edit
  affordance after save/cancel.
- Mobile/responsive: works inside the existing v0.4.0 stacked-card layout.
- WCAG 2.1: editor input has a visible label (`aria-label`), errors expose
  `aria-live="polite"`, focus management is preserved.

## Non-Goals

- Multi-cell or multi-row "save all" UX (Django allows it; we don't need it
  yet — keep MVP small).
- Optimistic UI / rollback on server failure — the server is the source of
  truth, the cell only swaps after the server response.
- Optimistic concurrency control — covered by epic 6.2.3, out of scope here.
  We defer "concurrent edit" detection to that epic; the BDD scenario below
  describes the *graceful* behaviour when a stale value is overwritten.
- Editing primary keys, relations, or computed fields. PK is never editable.
  Relation/FK editing inline is a future scope item.
- New ORM features. The existing `BaseAdapter.update(pk, data)` is reused.

## BDD Scenarios

```
Scenario: editable cell renders an edit affordance
  Given the User model declares list_editable = ["name"]
  And   the user list contains Alice
  When  the user opens /admin/user
  Then  Alice's name cell contains a button with data-testid "cell-edit-name"
  And   non-editable cells (e.g. email) do not contain such a button
```

```
Scenario: opening the editor swaps the cell to an inline input
  Given the User model declares list_editable = ["name"]
  When  the user clicks the edit affordance on Alice's name cell
  Then  the cell is replaced by an inline form with an input pre-filled
        with "Alice"
  And   the input is focused
  And   Save and Cancel buttons are present
```

```
Scenario: saving a valid value persists and re-renders the cell
  Given the inline editor for Alice's name cell is open
  When  the user types "Alicia" and clicks Save
  Then  the database row's name field is "Alicia"
  And   the cell is re-rendered with the new value
  And   an aria-live region announces "Saved"
```

```
Scenario: invalid input shows an error fragment without persisting
  Given the User model declares list_editable = ["name"]
  And   the User schema requires name min_length=1
  And   the inline editor for Alice's name cell is open
  When  the user clears the input and clicks Save
  Then  the response status is 422
  And   the cell shows a field-error list with data-testid "name-errors"
  And   Alice's name in the database is still "Alice"
```

```
Scenario: cancelling restores the static cell
  Given the inline editor for Alice's name cell is open
  When  the user clicks Cancel
  Then  the cell is restored to its read-only form with the original value
  And   no request is made to the update endpoint
```

```
Scenario: non-editable field cannot be POSTed inline
  Given the User model does NOT declare email as list_editable
  When  a POST is sent to /admin/user/{id}/inline/email
  Then  the response status is 403
  And   the user record is unchanged
```

```
Scenario: keyboard shortcuts save and cancel
  Given the inline editor for Alice's name cell is open
  When  the user presses Enter inside the input
  Then  the form submits as a Save
  And   when in a separate session the user presses Escape
  Then  the editor is cancelled and the static cell restored
```

## Design

### Architecture

Affected modules:

```
core/options.py        ─►  add list_editable: list[str] = []
core/model.py          ─►  expose list_editable on ModelAdmin
adapters/sqlmodel.py   ─►  reuse update(pk, data) — no change
views/dynamic.py       ─►  add inline_edit_form_view + inline_save_view
                           on DynamicModelView
routing.py             ─►  register two routes per model:
                             GET  /<model>/<id>/inline/<field>
                             POST /<model>/<id>/inline/<field>
templates/components/
  inline_cell.html     ─►  static cell + edit button (new)
  inline_editor.html   ─►  inline form fragment (new)
  inline_cell_error.html ─►  error fragment (new)
  table.html           ─►  use inline_cell.html instead of inline {{item[field]}}
static/css/
  hyperadmin.css       ─►  append minimal .ha-cell-edit / .ha-inline-editor
                           styles (no new framework)
```

Dependency direction stays inward — `views/` consumes `core/` options and
delegates persistence to the adapter via the existing `update()` contract.
No `core/` ↔ `views/` cycles introduced.

### Data Model Changes

No data model changes. Editing reuses `model.model_fields` for field metadata
and `PydanticForm.validate()` for validation, scoped to a single field.

### API / Protocol Changes

New view methods on `DynamicModelView`:

```python
async def inline_edit_form_view(
    self, request: Request, item_id: int, field: str
) -> Response: ...
async def inline_save_view(
    self, request: Request, item_id: int, field: str
) -> Response: ...
```

New routes per model (when `options.can_edit` is true and
`list_editable` is non-empty):

| Method | Path                                        | Name                            |
|--------|---------------------------------------------|---------------------------------|
| GET    | `/<model>/{item_id:int}/inline/{field:str}` | `<model>-inline-edit-form`      |
| POST   | `/<model>/{item_id:int}/inline/{field:str}` | `<model>-inline-save`           |

New configuration on `AdminOptions`:

```python
list_editable: list[str] = Field(default_factory=list)
```

Empty list ⇒ feature dormant (no buttons rendered, no routes activated).

### Configuration Changes

`AdminOptions.list_editable` is the single new option. It is opt-in.

`ModelAdmin` subclasses can either pass `options=AdminOptions(list_editable=[...])`
at registration time, or set a class-level `list_editable: list[str] = [...]`
attribute that the registry merges into options (kept consistent with how
existing options like `can_edit` work).

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `field` not in `list_editable` | View returns HTTP 403 with text "Field not editable". No DB read. |
| `field` not on the model schema | Same as above (treated as not editable to avoid leaking model shape). |
| Item not found (`pk` missing) | HTTP 404 via existing `HTTPException` pattern. |
| Validation error | HTTP 422, `inline_cell_error.html` fragment with field-error list. The static cell is *not* swapped to the new value. |
| `id`/PK field requested | Treated as not editable → 403. |
| Concurrent overwrite (last-writer-wins) | The server applies `update(pk, {field: value})` and re-renders. No locking. Optimistic concurrency is deferred to epic 6.2.3. |
| HTMX request without `hx-request` header (curl, direct POST) | The endpoints still work; they just return raw HTML fragments. CSRF protection is out of scope (no CSRF middleware exists project-wide today). |

## Migration & Backward Compatibility

Backward compatible — no migration required. Existing list views render
unchanged when `list_editable` is empty (the default). Templates fall back to
plain `{{ item[field] }}` when the field is not in the allow-list.

## Open Questions

- [ ] Should we add per-row `aria-live` regions or a single page-level one?
      Decision below: page-level region is simpler and sufficient for MVP.
- [ ] Should keyboard `Tab` move focus to the next editable cell? Out of
      scope for MVP; users can press Escape and Tab from the row.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Approval is dispatch-authorized | Yevhenii pre-authorized implementation in the agent dispatch for v0.5.0 close-out. SDD remains in `Draft` for record. | Wait for human gate (would block delivery). |
| Per-cell endpoint (`/<id>/inline/<field>`) instead of generic per-row patch | Lets us reuse the existing `BaseAdapter.update(pk, data)` contract, keeps per-field permission checks simple, and matches HTMX swap targeting one DOM element. | Single `/inline` endpoint accepting a JSON patch — wider blast radius, harder to swap a single cell back. |
| Allow-list (`list_editable`) opt-in, not opt-out | Safer default — makes the feature explicit per ModelAdmin. Matches Django convention. | Opt-out via `list_readonly` — easy to forget, larger blast radius. |
| Reuse `PydanticForm.validate` on a single-field dict | Keeps validation rules consistent with the full update form (min_length, type, etc.). | Hand-rolled per-field validation — duplicates rules. |
| Page-level aria-live region | One container with `aria-live="polite"` is simpler than per-row regions and matches a single-active-editor UX. | Per-cell aria-live — verbose, harder to manage. |
| Deferred OCC | Epic 6.2.3 owns optimistic concurrency. Inline cell editing should not pre-empt it. | Stamp `updated_at` and reject — premature for v0.5.0. |
