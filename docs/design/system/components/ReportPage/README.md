A declarative report: aggregates per row group and time bucket, with period and filters, an optional chart, CSV and Excel export, and a crosstab that scrolls inside its own wrapper. It is provided by the `hyperadmin-reports` plugin.

**Template:** `hyperadmin_reports/templates/reports/list.html` (index) and `detail.html` (report), reusing the Chart frame (`ha-chartframe`, `chart-frame`) and the table base. Spec: `docs/specs/olap-reporting.md`.

**The view provides:** label, one-line description, slug, the resolved period and bucket (including what Auto picked), active filters, the grid (row groups, column levels, cells with value and kind, row totals, column totals, grand total), and the export URLs carrying the current query string.

- **Sidebar:** one "Reports" nav group, with one entry per registered report the user may view (`view_report_{slug}`) and the `bar-chart-3` icon. The optional index page (`.ha-report-index`) is a grid of `.ha-report-card`s: title link (the whole card is the target), one sentence, and a caption saying what it aggregates.
- **Header:** crumbs (Reports › name), H1, description (`.ha-report-head__lede`), then a meta line with the period and the active filters as removable chips. Export is a Menu with CSV and Excel; both links keep the current query string. The menu label says "Uses the current period and filters".
- **Bucket switch:**
  - `.ha-seg` of submit buttons in a GET form (`name="period"`): Auto · Day · Week · Month · Quarter · Year. It works without JavaScript and wraps on narrow screens.
  - When Auto is pressed, a note names the bucket it chose and why ("Auto: quarter, for a 12-month range"). The rule is: up to 31 days by day, up to 92 by week, up to 186 by month, up to 1,100 by quarter, otherwise by year.
- **Filters:** the FilterSidebar or the FilterBar, with the same query keys as list views.
- **Chart (optional):** the existing Chart frame above the grid.
- **CrosstabTable (`.ha-xtab` inside `.ha-table-wrap.ha-xtab-wrap`):**
  - Layout:
    - The wrapper is capped at `min(70vh, 40rem)` and scrolls both ways inside itself. The page never scrolls sideways.
    - The row-group column is sticky on the start side (`.ha-sticky-first`). Both header rows stick: the second sits under the first at `--ha-row-h`.
  - Headers:
    - Multi-level column headers use `<th scope="colgroup" colspan>` for the year, then `<th scope="col">` for the buckets.
    - Bucket labels are as the spec formats them ("2026-01", "2025-Q3"). Short visible labels such as Q1 carry `<abbr title="2025-Q1">` and screen-reader text.
    - A hairline at the start of each group (`.ha-xtab__start`).
  - Row groups (`th scope="rowgroup"`) are quiet bands.
  - Totals:
    - The totals column (`.ha-xtab__total`) and the totals row (`<tfoot>`, also sticky at the bottom) use the page surface and semibold text.
    - They are separated by a hairline or a 2px rule. They are not coloured.
  - Values:
    - All numbers are `.ha-num`.
    - Text aggregates (comma-joined) truncate with `.ha-trunc` and focus to unfold.
    - Related-record aggregates are links, falling back to the raw pk in mono.
  - **Null vs zero:**
    - Null (no rows in that bucket) is `—` with the screen-reader text "no data".
    - Zero (rows that add up to zero) prints `€ 0` in normal text.
    - A key under the grid says which is which.
  - **Empty result:** one full-width "No data" cell that names the period and offers "Clear filters".
- **States:**
  - Loading: skeleton grid with `aria-busy="true"`.
  - Empty.
  - 403: the error card with the permission to ask for.
  - Filter parse error: the list-view decoration, with an invalid chip and the message under the field. The grid renders without the bad filter and says so.
  - 36 months: compact density, with the wrapper focusable (`tabindex="0"`, `role="region"`, a label that mentions it scrolls).
- **RTL:** the sticky column moves to the right, and the numbers and bucket labels stay LTR.

**Test ids:** `sidebar`, `nav-report-{slug}`, `report-index`, `report-export`, `report-export-csv`, `report-export-xlsx`, `report-period`, `report-grid`, `report-no-data`, `report-forbidden`, `filter-{field}-error`, plus the chart ids (`chart-frame`, `chart-{key}`, `chart-data-table-{key}`).

**Don't:**
- Colour cells by value, which would be a heatmap. That is not in scope, and colour alone would carry meaning.
- Print 0 for a missing bucket.
- Let the grid widen the page.
- Export without the current filters.
