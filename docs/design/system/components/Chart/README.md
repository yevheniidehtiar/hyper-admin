Server-rendered SVG line, bar and stacked-bar charts inside a chart frame with period switch, legend, table fallback and loading, no-data and error states.

**Template:** `components/charts/line.html`, `bar.html`, `stacked_bar.html`, `sparkline.html`, `frame.html` — Jinja2 macros that take already-aggregated, already-thinned points.

**The view provides:** series (name, points, unit), x labels formatted for the locale, y ticks, a one-sentence takeaway for `<desc>`, and the period options.

- **Frame** (`.ha-card`): title `ha-h4` + muted caption (period, unit), tools on the end side: `.ha-seg` period switch (`aria-pressed`; each option is also a link `?period=6m`, upgraded with `hx-get`), and a legend with text (`.ha-legend`). Body: the SVG, then `<details class="ha-details">Show as table</details>`.
- **SVG:** `class="ha-chart"`, `viewBox` sized to the design width, `<title>` + `<desc>`. With focusable tooltip points it is `role="group"` + `aria-labelledby`/`aria-describedby` (a `role="img"` would hide the points from screen readers); without them (sparkline, export) `role="img"`. The plot is `direction: ltr` in RTL pages. Gridlines `.grid` (`ha-chart-grid`), zero line `.axis`, tick text in `ha-chart-axis` 12px tabular.
- **Line:** one `<path class="line s1">` per series, 2px; series 2 is also dashed. Label series at the line's end when there is room (`.lbl`); otherwise rely on the legend.
- **Bar / stacked bar:** `<rect class="f1…f6">`, 60 % of the band; stacked segments separated by a 1px `ha-surface-raised` line; value labels on simple bars.
- **Tooltip:** each point is a `<g>` with a transparent hit rect (`tabindex="0"`, `aria-label` with all values for that x), the point circle and a `.tip` group; it shows on hover, keyboard focus and tap.
- **States:** loading = skeleton block of the chart's height with `aria-busy`; no data = empty state with the chart icon and the reason; error = danger text + Retry button that re-requests the fragment.
- **RTL:** the frame mirrors; the plot keeps time running left-to-right; the table fallback is `dir="ltr"`.
- **Optional interactive layer:** only with `interactive=True` on report pages; vendored, pinned, lazy. Never required to see the chart.

**Test ids:** `data-testid="chart-frame"`, `"chart-<key>"` on the SVG.
