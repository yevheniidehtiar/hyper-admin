# SDD: Optimistic Concurrency Control (OCC)

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #332 (epic), #314–#321 (stories) |
| Milestone | v0.6.0 — Real-Time Layer (Track B, independent of WebSocket track) |
| Created | 2026-05-10 |
| Last updated | 2026-05-10 |

---

## Problem

When two admins open the same record and save in sequence, the second save silently
overwrites the first. v0.5.0 shipped inline cell editing — an interaction pattern that
specifically encourages quick, cell-at-a-time edits — making the lost-update problem
more visible. The v0.5.1 SDD explicitly deferred OCC to a follow-up epic.

What's missing today:

1. **Conflict detection.** No version field is read or compared on update.
2. **Adapter contract.** `BaseAdapter.update(pk, data)` ignores prior state.
3. **View-layer signalling.** No HTTP 409 response, no conflict-resolution UI.
4. **OCC for inline cell editing.** The new endpoint shipped in v0.5.0 has no version field.

OCC is the smallest of the four v0.6.0 epics, has no dependency on WebSocket / PubSub
infrastructure, and provides immediate value to inline editing. Shipping it first inside
v0.6.0 lets the WebSocket track proceed in parallel with no merge contention.

## Goals

- **Auto-detect a version field** on each model: prefer an explicit `version: int` column;
  fall back to `updated_at: datetime` when settings allow it.
- **Adapter enforcement.** `BaseAdapter.update(pk, data, expected_version)` raises a
  typed `StaleRecordError` when the row's current version differs from `expected_version`.
- **View-layer wiring.** Update form renders a hidden `__version` field; on submit, view
  passes it through; on `StaleRecordError`, view returns HTTP 409 and renders a conflict
  dialog comparing the user's edits to the current values.
- **Inline cell editing integration.** Inline endpoints accept `__version` from the cell
  fragment; on conflict, the cell re-renders with a small "Refresh, your value is stale"
  affordance instead of swapping the value.
- **Opt-in per `ModelAdmin`.** `AdminOptions.enforce_occ: bool = False` (default off) so
  existing apps see no behaviour change; flip on once their models have a version column.
- **Settings switch for `updated_at` fallback.** `concurrency_use_updated_at: bool = False`.
  Documented as approximate (sub-millisecond races possible).
- **Friendly conflict resolution UI.** A diff dialog shows the user's submitted values vs.
  the current row, with "Override anyway" and "Discard my edits" actions.
- **Backward compatible.** `enforce_occ=False` ⇒ identical to current behaviour.

## Non-Goals

- Pessimistic locking (DB-level row locks held across HTTP requests). Always lossy on the
  open web; out of scope.
- Multi-row / batch update OCC. Bulk operations are not yet a first-class feature.
- Distributed lock managers (Redis lock). YAGNI for MVP; OCC is a server-side compare.
- Field-level conflict resolution ("merge their change in field X with my change in field
  Y"). Defer — would require structural diff and cell-level merging UI.
- Three-way merge with the original snapshot. The dialog is two-way (submitted vs.
  current); the user chooses one.
- Real-time notification of in-progress edits ("alice is editing this row"). That is the
  Presence epic (v0.6.0 Track D), not OCC.
- Versioned audit log of all changes. Audit log is its own SDD (deferred from v0.5.1).

## BDD Scenarios

```
Scenario: version field is auto-detected on a model with `version: int`
  Given a SQLModel Order has fields including version: int
  When  the framework introspects the model
  Then  the detected version_field is "version"

Scenario: updated_at fallback when version column is absent
  Given a SQLModel Order has updated_at: datetime but no version column
  And   concurrency_use_updated_at = True
  When  the framework introspects the model
  Then  the detected version_field is "updated_at"

Scenario: no version field detected when neither is present
  Given a SQLModel Tag has no version and no updated_at column
  When  the framework introspects the model with enforce_occ=True
  Then  a clear ConfigurationError is raised at startup

Scenario: update succeeds when expected_version matches current
  Given order#42 has version=3
  When  adapter.update(42, {"name": "Alice"}, expected_version=3) is called
  Then  the row is updated
  And   the new version is 4

Scenario: update raises StaleRecordError when expected_version is stale
  Given order#42 has version=3
  When  adapter.update(42, {"name": "Alice"}, expected_version=2) is called
  Then  StaleRecordError is raised with current=3, expected=2

Scenario: update form renders hidden __version field
  Given OrderAdmin.options.enforce_occ = True
  And   order#42 has version=3
  When  GET /admin/order/42/edit is rendered
  Then  the form contains an <input type="hidden" name="__version" value="3">

Scenario: update view returns 409 on stale submit
  Given OrderAdmin.options.enforce_occ = True
  And   order#42 has version=3
  When  POST /admin/order/42/edit is submitted with __version=2 and updated fields
  Then  the response status is 409
  And   the response renders the conflict dialog
  And   the dialog shows the user's submitted values vs the current row

Scenario: conflict dialog "discard my edits" navigates to a fresh edit form
  Given the user is on the conflict dialog after a stale submit
  When  the user clicks "Discard my edits"
  Then  the response is 302 to /admin/order/42/edit
  And   the form is rendered with current values

Scenario: conflict dialog "override anyway" re-submits with current version
  Given the user is on the conflict dialog with the current version=4
  When  the user clicks "Override anyway"
  Then  the form is re-submitted with __version=4
  And   the update succeeds (assuming no further concurrent change)
  And   the new version is 5

Scenario: inline cell save returns 409 on stale version
  Given OrderAdmin.options.enforce_occ = True
  And   list_editable = ["name"]
  And   order#42 has version=3
  When  POST /admin/order/42/inline/name with __version=2 and value="Alicia"
  Then  the response status is 409
  And   the cell re-renders showing the current value with a "Stale, refresh" indicator
  And   the row is unchanged

Scenario: enforce_occ=False preserves legacy behaviour
  Given OrderAdmin.options.enforce_occ = False (default)
  When  two concurrent updates both POST without __version
  Then  both updates succeed (last write wins, as today)
  And   no StaleRecordError is raised

Scenario: superuser does NOT bypass OCC
  Given a superuser request
  And   OrderAdmin.options.enforce_occ = True
  When  POST /admin/order/42/edit with stale __version
  Then  the response is 409
  And   the row is unchanged

Scenario: missing __version field on a configured model returns 400
  Given OrderAdmin.options.enforce_occ = True
  When  POST /admin/order/42/edit with no __version field
  Then  the response is 400 Bad Request
  And   the row is unchanged

Scenario: updated_at fallback rejects sub-millisecond stale writes
  Given concurrency_use_updated_at = True
  And   order#42 has updated_at = "2026-05-10T12:00:00.123Z"
  When  POST /admin/order/42/edit submits __version with a different timestamp
  Then  the response is 409

Scenario: prefetched form does not become stale until submit
  Given alice opens the edit form for order#42 (version=3)
  And   bob saves order#42 a moment later (now version=4)
  When  alice opens a different page and returns to the still-loaded form
  Then  alice's form still shows __version=3
  And   submitting it returns 409 with the conflict dialog
```

## Design

### Architecture

```
                       ┌─────────────────────────────┐
                       │  core/concurrency.py        │   (new)
                       │  ─ detect_version_field()   │
                       │  ─ StaleRecordError         │
                       └─────────────┬───────────────┘
                                     │ used by
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     core/adapters.py        adapters/sqlmodel.py    adapters/sqlalchemy.py
     (BaseAdapter contract)  (impl with WHERE pk    (impl with WHERE pk
       update(pk, data,        AND version=:v)       AND version=:v)
       expected_version=None)
              ▲                      ▲                      ▲
              │ called by                                   │
              ▼                                             │
     views/dynamic.py                                       │
     ─ update_view raises 409 on StaleRecordError, renders  │
       conflict_dialog.html                                  │
     ─ inline_save_view returns inline_cell_stale.html      │
              ▲                                             │
              │ render                                      │
              ▼                                             │
     templates/components/                                  │
     ─ conflict_dialog.html         (new)                   │
     ─ inline_cell_stale.html        (new)                   │
     ─ form.html                     (mod) hidden __version │
     ─ inline_cell.html              (mod) data-version attr│
```

Module layout:

```
src/hyperadmin/core/
└── concurrency.py            (new) — version detection + StaleRecordError

src/hyperadmin/adapters/
├── sqlmodel.py               (mod) — update(pk, data, expected_version)
└── sqlalchemy.py             (mod) — same

src/hyperadmin/core/
├── adapters.py               (mod) — BaseAdapter contract update
├── options.py                (mod) — enforce_occ
└── settings.py               (mod) — concurrency_use_updated_at

src/hyperadmin/views/
└── dynamic.py                (mod) — handle __version on update + inline_save

src/hyperadmin/templates/
├── form.html                 (mod) — hidden __version
└── components/
    ├── conflict_dialog.html  (new) — full-form conflict UI
    ├── inline_cell.html      (mod) — data-version attr on cell
    └── inline_cell_stale.html (new) — stale indicator + refresh affordance

tests/unit/test_concurrency.py
tests/unit/test_occ_adapters.py
tests/e2e/test_occ_conflict.py
```

`core/concurrency.py` lives in `core/` (no ORM-specific dependencies) — it only knows
about model field metadata and exception types.

### Data Model Changes

The framework adds **no columns** to its own tables. OCC works against host-application
columns:

- Recommended: `version: int = Field(default=1)` on any model that opts into OCC.
- Fallback: `updated_at: datetime` when `concurrency_use_updated_at=True`. Documented as
  approximate (timestamp resolution / clock skew can produce false negatives at sub-
  millisecond scale; rare in practice).

Detection precedence (in `detect_version_field()`):

1. If the model declares `__version_field__: ClassVar[str] = "..."`, use it.
2. Else if a `version: int` field exists, use it.
3. Else if `concurrency_use_updated_at` is `True` and `updated_at: datetime` exists, use it.
4. Else if `enforce_occ=True`, raise `ConfigurationError` at `Admin.__init__`.
5. Else, OCC is silently disabled for this model (legacy behaviour).

### API / Protocol Changes

**`StaleRecordError`** in `src/hyperadmin/core/concurrency.py`:

```python
class StaleRecordError(Exception):
    def __init__(self, *, model: type, pk: Any, expected: Any, current: Any) -> None: ...
```

**`BaseAdapter.update`** signature change:

```python
async def update(
    self,
    pk: Any,
    data: dict[str, Any],
    *,
    expected_version: Any | None = None,
) -> Any:
    """Update a row.
    If ``expected_version`` is provided, raise :class:`StaleRecordError` when the
    current version differs.
    """
```

`expected_version=None` preserves today's behaviour for adapters that pre-date OCC.

**SQLModel adapter implementation** (illustrative):

```python
async def update(self, pk, data, *, expected_version=None):
    vf = self._version_field
    async with self.session_factory() as session:
        if expected_version is not None and vf is not None:
            stmt = update(self.model).where(self.model.id == pk,
                                            getattr(self.model, vf) == expected_version)
            stmt = stmt.values(**data, **{vf: _bump(vf, expected_version)})
            result = await session.execute(stmt)
            if result.rowcount == 0:
                current = await session.get(self.model, pk)
                raise StaleRecordError(model=self.model, pk=pk,
                                       expected=expected_version,
                                       current=getattr(current, vf, None))
            await session.commit()
            # Re-fetch to return the canonical updated row
            return await session.get(self.model, pk)
        else:
            return await super().update(pk, data)
```

`_bump(vf, current)` increments integer versions and refreshes `updated_at` to
`datetime.now(UTC)`.

**View-layer changes** in `views/dynamic.py`:

```python
async def update_view(self, request, item_id):
    form = await self._build_form(request, item_id)
    expected_version = form.data.pop("__version", None)
    try:
        await self.adapter.update(item_id, form.data, expected_version=expected_version)
    except StaleRecordError as exc:
        current = await self.adapter.get(item_id)
        return self._render_conflict_dialog(request, submitted=form.data, current=current)
    return RedirectResponse(...)
```

A parallel branch in `inline_save_view` returns `inline_cell_stale.html`.

**`AdminOptions`** addition:

```python
enforce_occ: bool = False
```

**Public exports** added to `hyperadmin.__init__`:

```python
from hyperadmin.core.concurrency import StaleRecordError
```

### Configuration Changes

| Variable | Default | Description |
|---|---|---|
| `HYPERADMIN_CONCURRENCY_USE_UPDATED_AT` | `False` | Allow `updated_at` as a fallback version field |
| `HYPERADMIN_OCC_RENDER_DIALOG` | `True` | If `False`, return raw 409 with JSON body (for API clients) |

Per-`ModelAdmin`:

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(enforce_occ=True)
```

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `enforce_occ=True` but no version field detectable | `ConfigurationError` at startup. Fail fast |
| `enforce_occ=True` and the form posts no `__version` | 400 Bad Request — hostile / malformed client |
| `enforce_occ=False` and `__version` is present | Ignored. Forward-compat, no error |
| Multiple concurrent updates from the same user (two tabs) | Whichever submits second receives 409 |
| Override-anyway round-trip after the row changed *again* | Second 409. UI loops correctly |
| `updated_at` field with no timezone | Coerce to UTC at compare time. Documented |
| `updated_at` with database-side `NOW()` triggers | Works — adapter re-fetches after update |
| Custom version field name | Set `__version_field__: ClassVar[str] = "rev"` on the model |
| Bulk delete includes a stale row | Bulk operations bypass OCC in MVP. Documented; revisit when bulk update lands |
| Inline cell save with stale __version | 409 + `inline_cell_stale.html` (small "Refresh" indicator). Cell does not swap |
| Detail view (read-only) | OCC has no effect; reads are always best-effort |
| File upload field with OCC | Works — the file write happens after the version compare passes |
| Form re-render on validation error | `__version` re-emitted from the now-current value (refresh-aware) — actually no, we keep the original `__version` so the user can still resolve their conflict on resubmit. Documented |
| Object-level permission denial after OCC pass | Permission check runs first (existing v0.5.1 path); OCC compare runs only if permission granted |
| Tenant filter mismatch | The pre-update `adapter.get(pk)` already 404s for cross-tenant; OCC never executes |
| API client wants a raw 409 | `HYPERADMIN_OCC_RENDER_DIALOG=False` returns `{"error": "stale", "current_version": ...}` |
| Two updates with identical version values (e.g. trigger increments concurrently) | DB constraint or atomic `UPDATE WHERE version=:v` prevents — only one increments. The other gets 0 rows and 409 |

## Migration & Backward Compatibility

- **No breaking changes.** `enforce_occ=False` (default) preserves current behaviour.
- **`BaseAdapter.update` signature** gains a keyword-only `expected_version=None`.
  Third-party adapters that don't accept it: callers will pass it as a kwarg, raising
  `TypeError`. Mitigated by adding the kwarg with default `None` to the protocol; runtime
  callers only pass it when `enforce_occ=True`. Documented.
- **DB migration owned by host app.** When opting into OCC, add `version: int default 1`
  to the relevant model. Documented in changelog.
- **Public API.** `__init__.py` gains `StaleRecordError`. Nothing renamed.
- **Inline cell editing.** The inline `__version` data attribute is additive on the cell
  fragment; absent cells render as today.

## Open Questions

- [x] Where does version detection live — adapter or core? → **`core/concurrency.py`.**
      Pure metadata inspection; no ORM dependency. Adapters consume the helper.
- [x] What's the fallback when no version field exists and `enforce_occ=True`? →
      **`ConfigurationError` at startup.** Better than silently degrading to last-write-
      wins.
- [x] Auto-bump strategy for integer versions? → **`current + 1`** in the same UPDATE
      statement (atomic, no race with the SELECT).
- [x] Show conflict dialog vs auto-merge? → **Show dialog.** Auto-merge is a research
      problem and silently swallows intent.
- [x] What does the inline cell stale indicator look like? → A small "stale" badge on the
      cell + a "Refresh" link. Submission re-runs the inline GET to fetch the current value.
- [ ] Should OCC be ON by default in v0.7? → Likely yes once host apps have had a release
      to add version columns. Tracked separately; **not a blocker** for v0.6.0.
- [ ] OCC interaction with bulk operations? → Bulk update isn't a feature yet. When it
      lands, OCC will need a per-row check. **Out of scope** for this SDD.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Optimistic concurrency, not pessimistic | Web-scale interactive UI; pessimistic locks held across HTTP are toxic | Pessimistic — rejected, doesn't survive abandoned tabs |
| Atomic `UPDATE WHERE pk=? AND version=?` | Single round-trip; race-free | SELECT + UPDATE — needs serializable isolation |
| Auto-detect version field with override | Most apps will use `version: int`; flexibility for legacy schemas | Force every app to declare — friction |
| `updated_at` fallback off by default | Approximate (clock-skew, sub-ms races); explicit opt-in | On by default — surprising false positives |
| Opt-in per `ModelAdmin` | Existing apps must see no change after upgrade | On by default — breaks every existing install |
| Conflict dialog renders submitted vs current | Lets user pick winner without losing their edits | Auto-discard / auto-override — silent data loss either way |
| `StaleRecordError` exposed publicly | Lets host apps catch and translate as they need | Internal — would force host apps to catch generic Exception |
| Inline cell stale indicator (not full dialog) | A full-page dialog over a single-cell edit is jarring | Full dialog for inline too — UX whiplash |
| Render mode toggle (HTML dialog vs JSON 409) | Same routes serve both UI and API clients | Two route prefixes — duplication |
| OCC uses `expected_version` keyword-only | Future-proof against positional ambiguity | Positional — easier to misuse |
| Track B independent of WebSocket track | OCC has zero infra dependency on PubSub; ship it first inside v0.6.0 | Bundle into a single epic — slows OCC delivery |
