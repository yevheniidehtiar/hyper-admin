# SDD: HTMX FK/M2M Autocomplete with Dependent Filtering and Inline Create

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

The existing relation widget surface (`views/dynamic.py:choices_view`,
`core/fields.py:classify_field`, `views/forms.py`) renders FK and M2M fields
as static `<select>` elements populated via a single HTMX endpoint
(`GET /{model}/choices/{field_name}`). It is *partial* because:

1. **No dependent filtering UX.** `choices_view` already forwards arbitrary
   extra query params to `adapter.get_choices()`, but no widget pattern wires
   one select's value to another's `hx-include`. Consumers reinvent this with
   ad-hoc JavaScript every time.
2. **No inline create.** When an admin needs to pick a Supplier that doesn't
   exist yet, the user must abandon the form, create the Supplier elsewhere,
   then start over. Standard admin UX has a "+" affordance that opens a modal
   to create the related record without losing form state.
3. **No per-relation display template.** `choices_options.html` hard-codes
   how an option label is rendered. Consumers want richer option rows
   (`{name} — {city}, {country}`, possibly with thumbnails).

## Goals

- A standard FK/M2M autocomplete widget driven by HTMX with debounced search,
  no custom JavaScript required by consumers.
- A declarative way to express "field B's choices depend on field A's value"
  so the widget forwards the parent value via `hx-include`.
- A "+" button next to FK widgets that opens a popup form, creates the related
  record, returns the new pk, and inserts it into the parent form.
- A per-relation `display_template` so admin authors can customise option
  rendering without overriding the choices view.
- Backward compatibility: existing relation widgets keep working with no code
  changes; new behaviour is opt-in via `AdminOptions`.

## Non-Goals

- Pagination / infinite scroll inside the dropdown. `choices_view` already
  supports `limit`/`offset`; v0.5.5 keeps the current "show first 50, type to
  filter" UX. A virtualised dropdown is a v0.5.6+ task.
- Cross-admin popup creation. The "+" popup can only target a model that is
  also registered with the same `Admin()`.
- Server-rendered M2M tag inputs (chips). Deferred — multi-select is rendered
  as a multi-checkbox list in v0.5.5.
- Authoring custom widgets from scratch. We expose `display_template` and
  dependency wiring, not a full widget plugin API.

## BDD Scenarios

```
Scenario: FK field renders an autocomplete widget by default
  Given a ModelAdmin for Product with FK to Supplier
  When  the user opens /admin/products/create
  Then  the Supplier field renders as <input type="search"> with hx-get="/admin/products/choices/supplier_id"
  And   typing "ac" issues a debounced GET /admin/products/choices/supplier_id?q=ac

Scenario: dependent FK forwards the parent value via hx-include
  Given AdminOptions(relation_filters={"variant_id": {"depends_on": "supplier_id"}})
  When  the user selects supplier_id=42 and focuses the variant_id field
  Then  the variant_id widget's hx-get includes "?supplier_id=42"
  And   the dropdown lists only variants whose supplier_id == 42

Scenario: dependent FK with no parent value lists nothing
  Given the same dependent wiring
  When  the user focuses variant_id before choosing a supplier
  Then  the dropdown renders an empty <option> list
  And   the field shows placeholder "Pick a supplier first"

Scenario: "+" popup creates the related row and selects it
  Given the Supplier model is registered in the same Admin
  When  the user clicks "+" next to the supplier_id field on /admin/products/create
  Then  a modal loads /admin/suppliers/create-popup
  And   on save the modal closes
  And   the parent supplier_id field has the new supplier's id and label

Scenario: "+" popup is hidden when the related model is not registered
  Given Supplier is not registered with this Admin
  When  the user opens /admin/products/create
  Then  the Supplier field has no "+" button

Scenario: display_template renders custom option rows
  Given AdminOptions(relation_display={"supplier_id": "{name} — {city}"})
  When  the user types "ac" in the supplier_id widget
  Then  each <option> label is rendered as "{name} — {city}" for the matching row

Scenario: choices_view rejects unknown relation field
  When  GET /admin/products/choices/not_a_field is called
  Then  the response is 404 with detail "Unknown relation field: 'not_a_field'"
```

## Design

### Architecture

Touched modules:

```
core/options.py        — AdminOptions gains relation_filters, relation_display
core/fields.py         — classify_field carries dependent / display metadata
views/dynamic.py       — choices_view stays; new create_popup_view added
views/forms.py         — AutocompleteWidget renders search input + hx-get + hx-include
templates/widgets/     — autocomplete.html, choices_options.html (refined), popup_form.html
```

No new top-level module. The popup endpoint is an alias of the existing create
view with an HTMX-aware response that returns an `HX-Trigger` event carrying
the new row's `(id, label)` payload.

### Data Model Changes

No data model changes. `AdminOptions` gains two new optional fields:

```python
relation_filters: dict[str, RelationDependency] | None = None
relation_display: dict[str, str] | None = None
```

with:

```python
class RelationDependency(BaseModel):
    depends_on: str            # name of the parent field in the same form
    placeholder: str | None = None  # text shown when the parent is unset
```

### API / Protocol Changes

**New view:**

```python
async def create_popup_view(self, request: Request) -> Response: ...
```

Mounted at `POST /{model}/create-popup`. On successful create, returns:

```
HTTP 200
HX-Trigger: {"hyperadminPopupCreated": {"target": "<field_name>", "id": <new_pk>, "label": "<display>"}}
Content-Type: text/html
<empty body, modal closes via hx-on>
```

The label uses the related model's admin `relation_display` template if set,
or falls back to `str(instance)`.

**`choices_view`** is unchanged — it already accepts arbitrary extra query
params for cascading filters.

**Widget output template** (`widgets/autocomplete.html`) renders:

```html
<div class="ha-autocomplete" data-field="{{ field.name }}">
  <input
    type="search"
    name="{{ field.name }}_search"
    hx-get="{{ choices_url }}"
    hx-trigger="keyup changed delay:200ms"
    hx-target="next .ha-options"
    {% if field.depends_on %}
      hx-include="[name='{{ field.depends_on }}']"
      data-depends-on="{{ field.depends_on }}"
    {% endif %}
    data-testid="autocomplete-{{ field.name }}"
  >
  <select name="{{ field.name }}" data-testid="autocomplete-select-{{ field.name }}">
    {% include "widgets/choices_options.html" %}
  </select>
  {% if popup_url %}
    <button type="button" hx-get="{{ popup_url }}" hx-target="#ha-popup-root" data-testid="autocomplete-add-{{ field.name }}">+</button>
  {% endif %}
</div>
```

When `depends_on` is set, the widget also emits a tiny `hx-trigger="change from:[name='{{ depends_on }}']"` so changing the parent re-fetches options.

### Configuration Changes

`AdminOptions` adds `relation_filters` and `relation_display`. No env vars.
No `Admin()` constructor arg changes. Both fields default to `None`; the widget
falls back to its current behaviour when unset.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `depends_on` references a field that doesn't exist on the form | Raised at `AdminOptions` validation: `ValueError("depends_on='x' not in form fields")` |
| `relation_display` template references a missing attribute | Render falls back to `str(instance)`; warning logged once per template per process |
| Popup target model not registered | "+" button omitted client-side; server-side 404 if a crafted POST hits `create-popup` |
| `choices_view` parent param is unset and a `depends_on` is configured | Returns the empty-options fragment with the configured `placeholder` |
| User types fast | Debounce 200ms on the input prevents thrash; `choices_view` is safe to call concurrently |
| HTMX request without `hx-request` header (curl, manual test) | Endpoint still returns HTML fragment; no special handling required |
| Permission denied on popup create | Returns 403 with the standard error template; modal stays open with error |

## Migration & Backward Compatibility

Backward compatible. Existing widgets render unchanged when `relation_filters`
and `relation_display` are unset. `choices_view`'s contract is unchanged.

`AutocompleteWidget` replaces the default `<select>` for FK/M2M fields when
`AdminOptions.use_autocomplete_widget` is True. v0.5.5 defaults this to True
because the new widget is strictly a superset of the old select. Admins that
want the legacy select can set `use_autocomplete_widget=False`.

## Open Questions

- [ ] Should `relation_display` accept a callable in addition to a format string? Proposal: yes — `str | Callable[[Any], str]`. Format strings cover 80% of cases; callables let consumers reach into computed properties.
- [ ] Where does the popup modal live in the DOM? Proposal: a single `<div id="ha-popup-root">` added once to `base.html`. HTMX swaps the modal contents in/out; close via `hx-on::after-request="this.innerHTML=''"`.
- [ ] Should dependent filtering support more than one parent (`depends_on: ["a", "b"]`)? Proposal: defer; if needed, a follow-up extends `depends_on` to accept a list without breaking the single-string form.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Reuse existing `choices_view` for cascading filters | It already forwards arbitrary query params to the adapter; no new endpoint surface | New `/depends-choices/` endpoint per dependency |
| Single popup-root div in `base.html` | One slot, predictable target; matches HTMX idioms | Per-widget popup containers; Alpine.js modal store |
| Format-string `relation_display` (not full Jinja) | Format strings are safe by default and trivially serialisable; full Jinja would invite XSS via untrusted attribute access | `Template(...)` per relation; callable-only |
| Default `use_autocomplete_widget=True` | New widget is a strict superset; consumers benefit immediately | Default off — would mean v0.5.5 ships dormant |
| Popup uses `HX-Trigger` event, not `HX-Location` | Event carries the structured payload (id + label); page must not navigate away from the parent form | `HX-Location` (loses parent form state); inline `Set-Cookie` (fragile) |
