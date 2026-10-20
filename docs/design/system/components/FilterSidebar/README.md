The v0.5.6 filter library as a side panel beside the list. **Decision:** this is a layout variant of the FilterBar, not a new component. It uses the same GET form, query keys, chips, "Clear all" and error rules. Only the arrangement differs. Models with one or two filters keep the top FilterBar; the sidebar is for richer filter sets.

**Template:** `components/filter_sidebar.html` (new), included by `list_layout.html` when the model declares filters, plus one partial per filter type under `components/filters/`. Spec: `docs/specs/filter-library.md`.

**The view provides:** the filter definitions (type, field, label, choices or relation URL, default), the current values from the query string, the per-filter errors, the applied-filter chips, the saved views, and the result count.

- **Layout (`.ha-filterlayout` container):**
  - From 720px of container width: the list sits on the start side and an 18rem `.ha-filterside` sits at the end. It sticks under the navbar, and its body scrolls on its own.
  - Below 720px the panel is hidden. A "Filters (3)" button opens it as a sheet from the end edge (`.ha-filtersheet`, a modal `<dialog>`, `aria-labelledby` its heading) with a sticky Apply bar.
- **Panel:**
  - Head: "Filters" and a count of active filters, with Reset (a link to the bare list URL).
  - Body, in this order: My views (see SavedViews), then the filter groups.
  - Foot: "Clear all" and "Apply filters" (primary).
  - Each group is a `<fieldset class="ha-filtergroup">` whose legend carries a per-group "Clear" link.
- **Date range:**
  - Preset buttons (`.ha-presets`, `aria-pressed`): Today, This week, This month, Last month, This quarter. They submit `{field}__preset`.
  - From and To inputs (`type="date"`, `{field}__gte` and `{field}__lte`) in two columns.
  - If From is after To, both inputs get `aria-invalid`, the legend turns danger, and the message reads: "“From” is after “To”. Swap the dates or pick a preset."
- **Multi relation:** a search box over a checklist (`.ha-checklist`). Rows carry counts, and selected rows come first. "Show 18 more" is a link (`?{field}__more=1`) that HTMX enhances into an in-place fetch. Above about 50 options, use the Combobox multiple instead.
- **Multi choice:** a checklist of checkboxes (`{field}__in`).
- **Boolean:** tri-state Any · Yes · No as `.ha-seg--radio`. These are real radios, so the control submits without JavaScript and the selected state is bold, not only filled.
- **Mine only:** `.ha-switch` (`role="switch"`, `is_owner=1`), with a help line saying what "mine" means.
- **Current-period default:** an info hint inside the date group: "Showing this month by default." It has the link "Show all dates" (`?{field}=all`). The chip for a default filter says "this month", so it is never a silent filter.
- **Applying:**
  - With HTMX, each change does an `hx-get` of the list URL, `hx-target` the `<tbody>`, `hx-push-url` (the URL holds the state).
  - While the request runs, only the table wrap gets `aria-busy="true"`: rows dim and a 3px indeterminate bar runs along the top of the table (`.ha-table-loadbar`). A polite status says "Updating results", then the count.
  - The chips, panel, header and pager stay put.
  - Without JavaScript, Apply submits the form.

**Test ids:** `filter-sidebar`, `filter-{field}-gte`, `filter-{field}-lte`, `filter-{slug}-error`, `filter-{field}-default`, `filter-supplier-search`, `filter-supplier-more`, `filter-is_owner`, `filters-apply`, `filters-reset`, `filters-clear`, `applied-filters`, `list-table`.

**Don't:**
- Auto-apply on every keystroke in the relation search. That search only narrows the checklist.
- Fade the whole page while applying.
- Disable Apply when nothing changed.
- Put errors only in a toast.
