Search and filters above a list, with applied filters shown as removable chips.

**Template:** `components/filter_bar.html` (+ `components/filter_chips.html`).

**The view provides:** the search fields, a list of filters (text, select, multi-select, date range, number range, boolean), current values and validation errors.

- `<form class="ha-filterbar" role="search" aria-label="Filter invoices" method="get">` on `ha-surface-sunken`. It works as a plain GET form; HTMX upgrades it with `hx-get` and `hx-push-url` so the URL always holds the filter state.
- Search: `.ha-search` with a leading search icon and `type="search"`.
- Ranges: `.ha-range` is a `role="group"` with a label ("Amount range"); both inputs get `aria-invalid="true"` and an `.ha-errmsg` below the bar when from > to.
- Applied filters render as `.ha-chip` under the bar, each with a remove button labelled "Remove filter Status: Overdue"; an invalid one is `.ha-chip--invalid`. "Clear all" is a ghost button and only appears with two or more chips.
- Below `ha-bp-md` the filters collapse behind a "Filters (3)" button that opens them in the drawer; search stays visible.

**Test ids:** `data-testid="filter-bar"`, `"applied-filters"`, `"filters-clear"`.
