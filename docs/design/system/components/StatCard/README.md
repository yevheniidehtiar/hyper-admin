A single KPI with its change and an optional sparkline, for dashboards.

**Template:** `components/stat_card.html` macro `stat(label, value, delta=None, rising=None, good=None, series=None)`.

- `.ha-card.ha-stat`: label (13px muted), value (30px, tabular), delta, sparkline.
- **Delta** is arrow + signed percentage + "vs last month"; colour comes from whether the change is good, not its sign: pass `rising` for the arrow and `good` for the colour separately (overdue invoices +1 is an up arrow in `ha-color-danger-text`; days-to-get-paid −3 is a down arrow in `ha-color-success-text`), plus visually hidden text ", better" or ", worse". Arrows never mirror.
- **Sparkline:** a server-rendered SVG path (`.ha-spark`, 40px tall, `ha-chart-1`), decorative (`aria-hidden`) because the number and delta already say it; the full trend lives in a linked report.
- **Loading:** skeleton for value and delta, `aria-busy="true"`. **No data:** an em dash and one muted line saying why.
- In a grid of `minmax(200px, 1fr)`; at most four in a row.

**Test ids:** `data-testid="stat-<key>"`; the section's `aria-label` is the label.
