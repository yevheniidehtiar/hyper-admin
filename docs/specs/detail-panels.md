# SDD: Detail-page Panels & Tabbed Layout

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | TBD |
| Milestone | v0.5.6 — Detail Panels & Filter Library |
| Created | 2026-05-11 |
| Last updated | 2026-05-11 |

---

## Problem

Today `detail_view` (`src/hyperadmin/views/dynamic.py:detail_view`) renders one
template (`detail.html`) with a fixed `detail_fields` block. There is no way
for an admin author to compose multiple, optionally-async sections under the
same detail URL — e.g. "Invoice" (stream a PDF), "History" (custom rendered
event log), "Transitions" (state-machine diagram). Downstream consumers always
need at least one of those, and today they fork the detail template.

The H4 upstream check requires HyperAdmin to ship the **panel registry +
tabbed detail layout + one PDF-streaming demo panel**. Panel *content* for
History / Transitions is intentionally an extension point — consumer apps
register their own panels.

## Goals

- Declarative `panels: list[PanelDef]` on `AdminOptions` with a `@panel`
  decorator counterpart for class-defined panels.
- Tabbed detail layout that lazy-loads each panel's body via HTMX
  (`hx-get` + `hx-trigger="revealed once"`).
- Panel handlers may return `HTMLResponse` or `StreamingResponse` — the layout
  embeds HTML; streaming responses redirect the tab body to a dedicated
  download/inline URL (`Content-Disposition: inline`).
- One bundled demo: a built-in `PDFStreamPanel` factory that streams a
  static PDF stored in-tree, so the qualification check can exercise the
  streaming path without consumer code.
- Permission re-check per panel: `view_{model}_panel_{slug}` codename.

## Non-Goals

- WebSocket-driven live panels. Panels are HTTP fragments only.
- Cross-model panels. A panel is attached to one `ModelAdmin`.
- Editable panels. Panels are read-only in v0.5.6. Inline edit lives in its
  own epic (`epic-inline-cell-editing`).
- Persisted panel ordering per user. The order is whatever the admin author
  declares.

## BDD Scenarios

```
Scenario: detail page renders configured panel tabs
  Given AdminOptions(panels=[PanelDef(slug="invoice", label="Invoice", handler=...)])
  When  the user opens /admin/orders/42/
  Then  the page has a tab strip with one tab "Invoice"
  And   the tab's hx-get is "/admin/orders/42/panels/invoice"

Scenario: panel body lazy-loads when its tab becomes visible
  Given the same configuration
  When  the user clicks the "Invoice" tab
  Then  GET /admin/orders/42/panels/invoice is issued exactly once
  And   the response body replaces the tab content area

Scenario: streaming panel returns Content-Disposition inline
  Given a PDF panel returning StreamingResponse with media_type="application/pdf"
  When  the user clicks the tab
  Then  the tab content is replaced with an <iframe src="/admin/orders/42/panels/invoice/stream">
  And   GET on that stream URL returns "Content-Disposition: inline" and the PDF bytes

Scenario: panel handler raising HTTPException(403) surfaces a forbidden body
  Given a panel handler that raises HTTPException(403)
  When  the user clicks the tab
  Then  the tab body renders the standard 403 partial
  And   sibling tabs remain functional

Scenario: panel slug collision raises at registration
  Given AdminOptions(panels=[PanelDef(slug="x", ...), PanelDef(slug="x", ...)])
  When  the model is registered
  Then  ValueError is raised: "duplicate panel slug 'x'"

Scenario: permission codename gates panel access
  Given user lacks "view_order_panel_invoice"
  When  GET /admin/orders/42/panels/invoice is issued
  Then  response is 403
```

## Design

### Architecture

Touched modules:

```
core/panels.py        — NEW: PanelDef dataclass, @panel decorator, registry helper
core/options.py       — add panels: list[PanelDef] | None
views/dynamic.py      — _resolve_panels(), render_panel_view, stream_panel_view, route registration
templates/detail.html — tab strip + content slot
templates/components/panel_tab_strip.html — NEW
examples/full-demo/   — bundled PDF in tests/_fixtures/ to drive the streaming demo
```

No new top-level module — `panels` lives under `core/` next to `actions.py`.

### Data Model Changes

No DB tables. `PanelDef`:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PanelDef:
    slug: str
    label: str
    handler: Callable[..., Awaitable[Response]]
    icon: str | None = None
    permission: str | None = None   # default derived as f"view_{model}_panel_{slug}"
```

The `@panel(slug=..., label=...)` decorator marks a `ModelAdmin` method as a
panel handler with the same semantics as `@action`.

### API / Protocol Changes

**New view methods on `DynamicModelView`:**

```python
async def render_panel_view(
    self, request: Request, item_id: int, slug: str
) -> Response: ...

async def stream_panel_view(
    self, request: Request, item_id: int, slug: str
) -> Response: ...
```

Routes:

```
GET /{model}/{id}/panels/{slug}          → render_panel_view (HTML fragment)
GET /{model}/{id}/panels/{slug}/stream   → stream_panel_view (binary stream)
```

The render view inspects the handler's return type. If the handler returns a
`StreamingResponse`, the rendered fragment is `<iframe src=".../stream">` and
the actual stream is served from the dedicated `/stream` sub-route on demand.

`PDFStreamPanel` factory (bundled):

```python
def pdf_stream_panel(*, slug: str, label: str, path_resolver: Callable[[Any], Path]) -> PanelDef: ...
```

`path_resolver(instance) -> Path` returns the on-disk path; the factory wraps
it in a `StreamingResponse` with `Content-Disposition: inline` and
`media_type="application/pdf"`.

### Configuration Changes

`AdminOptions` gains `panels: list[PanelDef] | None = None`. When `None`, the
existing `detail.html` renders unchanged — no tab strip, no extra routes.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Duplicate slug at registration | `ValueError("duplicate panel slug 'x'")` |
| Slug not in registry | 404 with `"Unknown panel"` |
| Handler raises HTTPException | propagate; HTMX swap shows the error fragment |
| Handler returns non-`Response` | `TypeError` raised at request time, logged |
| Streaming handler returns wrong media type | accepted; the iframe wrapper hands display to the browser |
| Permission codename missing | derived default applied silently |
| Item not found | 404 before any panel handler runs |
| Multiple panels race-load | each is a separate request; no shared mutable state |

## Migration & Backward Compatibility

Backward compatible. Admins with no `panels` keep rendering `detail.html`
exactly as before. The tab strip template only renders when `panels` is set.
No database migration. `detail.html` gains a `{% if panels %}` guard around
the new tab markup.

## Open Questions

- [ ] Should panel handlers receive the loaded instance (`obj: Any`) directly, or only `request, item_id` like `@action`? Proposal: pass `obj` — saves every panel re-fetching, matches Django's `ModelAdmin.get_object()` ergonomics.
- [ ] Should the bundled `PDFStreamPanel` ship in `hyperadmin.panels.streams` or directly under `hyperadmin`? Proposal: `hyperadmin.panels` namespace (new package re-exported from `hyperadmin.__init__`).
- [ ] Should panels support an `enabled` predicate `(obj) -> bool` so a tab disappears for instances in the wrong state (e.g. an unpaid order has no Invoice tab)? Proposal: yes — `PanelDef.enabled: Callable[[Any], bool] | None`.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Lazy-load each tab via HTMX | Detail page stays fast; panel handlers can do expensive work without blocking initial render | Render all panels server-side up front; preload only the first |
| Streaming bodies live on a separate `/stream` sub-route, iframed | Browsers' Content-Disposition handling assumes a top-level navigation or iframe; HTMX swap of a binary body is ambiguous | Inline the stream in the swap (fails for binary); force download (breaks "Invoice in-tab" UX) |
| Default permission codename `view_{model}_panel_{slug}` | Lines up with object-permission machinery from v0.5.1 | Free-form perm string per panel; no perm by default (insecure) |
| Bundle one demo factory only (`PDFStreamPanel`) | Just enough to make the qualification check executable; History/Transitions live downstream | Ship History/Transitions stubs (out of scope per plan); ship no factory (fails the check) |
