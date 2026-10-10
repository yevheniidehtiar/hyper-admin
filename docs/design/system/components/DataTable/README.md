The change list: a sortable, selectable, filterable table of records that turns into stacked cards when the table itself is narrower than 768px.

**Template:** `components/table.html` (+ `components/bulk_actions.html`, `components/inline_editor.html`).

**The view provides:** columns (label, field, type from Column types, sortable, numeric), rows, current sort, selection support, bulk actions, inline-editable fields, empty/error message.

- Wrapper `.ha-table-wrap` (radius `ha-radius-lg`, scrolls horizontally inside itself, never the page). Table `.ha-table`; add `.ha-table--cards` to get the card layout when the wrapper is under 768px wide (a container query on `.ha-table-wrap`, so it also works in narrow panels and dialogs; every `<td>` needs `data-label`).
- Row height follows density: `ha-row-height` 44px comfortable, `ha-row-height-compact` 32px compact. Header row on `ha-surface-sunken`, sticky; first column can be sticky with `.ha-sticky-first`.
- The record's title cell is `<th scope="row">` with a link to its detail page.
- **Sorting:** header contains `<button class="ha-sort">`; the `<th>` carries `aria-sort="ascending|descending"` and the arrow icon (never mirrored). The active column label turns `ha-color-primary-text`.
- **Selection:** first column is a checkbox with a visually hidden label "Select INV-0142"; header checkbox "Select all on this page". The checked checkbox is the only state: the row turns `ha-surface-selected` through `tr:has(> .ha-col-check input:checked)` (or `.is-selected`). Do not put `aria-selected` on a `<tr>`; it is only valid inside a `role="grid"`. With one or more selected, `.ha-bulkbar` replaces the toolbar and says how many.
- **Hover** (`ha-surface-hover`) is a convenience only: row actions are always visible links/buttons.
- **Inline editing:** the cell swaps (HTMX) to `.ha-cell-edit` with an input labelled "Amount for INV-0141" plus Save and Cancel icon buttons; Enter saves, Esc cancels, focus returns to the cell.
- **Loading:** keep the header, render 3–10 skeleton rows (`.ha-skel`) and set `aria-busy="true"` on the wrapper. **Empty:** one `.ha-table-state` row with what was searched and a "Clear filters" link. **Error:** a danger alert with a Try again link above the empty table.
- Numbers, money and dates are `.ha-num`: tabular, end-aligned, `dir=ltr` isolated, so they line up in RTL too.

**Accessible names / test ids:** `<table aria-label="Invoices">` (the model's plural), wrapper `data-testid="changelist"`, rows `data-testid="row-<pk>"`, empty state `data-testid="changelist-empty"`.

**Don't:** put more than one link per row besides the title; truncate numbers; colour a row to mean status (use a pill in a status column).
