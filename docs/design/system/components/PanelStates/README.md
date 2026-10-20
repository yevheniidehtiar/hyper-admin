What goes inside a lazily loaded detail tab: loading, error, no access, hidden tabs, and a streamed document viewer. This extends DetailPanel.

**Template:** `components/detail_panel.html` (the tab panel shell), `components/panel_states.html` (loading, error and 403 fragments), `components/panel_document.html` (stream viewer). Spec: `docs/specs/detail-panels.md`.

**The view provides:** the visible panels (slug, label, count), with the `enabled` predicate already applied, the panel URL `/{model}/{id}/panels/{slug}`, the stream URL with file name and size for document panels, and the per-panel permission (`view_{model}_panel_{slug}`).

- **Loading:** the panel (`.ha-panel`, `role="tabpanel"`) fetches with `hx-get` and `hx-trigger="revealed once"`. Until it arrives it shows 3 or 4 skeleton lines with `aria-busy="true"` and the screen-reader text "Loading payments". The tabs, the summary and every other panel stay usable.
- **Error:**
  - `.ha-panel-state--error`: a danger glyph, "Payments didn’t load.", then one plain sentence ("The server took too long to answer. The other tabs still work.").
  - Retry is a link to `?tab=payments`, so it works without JavaScript; HTMX re-requests the fragment in place.
  - The error is `role="alert"` only after a user action. On the first load use a polite status.
- **403:** a lock glyph, "You don’t have access to this panel.", and the permission to ask for. The tab stays visible because the tab list doesn't know about the permission yet. If the server knows up front, it omits the tab.
- **Hidden tab:** when `enabled(record)` is false, the tab and its panel are not rendered at all, never shown as disabled. The remaining tabs close up, and arrow-key order follows what is shown.
- **Document panel (`.ha-docview`):**
  - Toolbar: file icon, file name (truncates), size, "Open in new tab" (ghost, `target="_blank"`, with the screen-reader text "(opens a new tab)"), and Download (`download`).
  - The frame is `.ha-docview__frame` (`/stream`). Height is `clamp(22rem, 70vh, 56rem)`, and it is full width on phones.
  - Use `<object type="application/pdf" data="…/stream">` with the fallback inside it rather than a bare `<iframe>`. Most phone browsers can't render PDFs inline, and `<object>` shows its own fallback when they can't.
  - Fallback text (`.ha-docview__fallback`): "This browser can’t show the PDF inside the page. Open it in a new tab or download it."
- Panels share the card padding (`--ha-pad-card`), so compact density tightens them too.

**Test ids:**
- `tab-{name}` (existing).
- `panel-{slug}`.
- `panel-retry`.
- `panel-pdf-viewer`.

**Don't:**
- Load every panel on page load.
- Blank the whole card on one panel's error.
- Show a disabled tab for a predicate that hides it.
- Auto-download the PDF.
