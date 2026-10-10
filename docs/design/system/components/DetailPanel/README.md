The read view of one record: summary header, tabs, field list, related lists and activity timeline.

**Template:** `detail.html` with `components/summary.html`, `components/tabs.html`, `components/related_list.html`, `components/timeline.html` (v0.5.6).

**The view provides:** the record's title, status, 2–4 key figures, the fieldsets, related models, and audit events.

- `<article class="ha-card">` labelled by the record title. **Summary** (`.ha-summary`): title in `ha-h2` with its status pill, a muted subline with the main relation and date, `.ha-kv` key figures, and the actions (Edit as secondary; Delete lives in the edit form or a menu).
- **Tabs:** `role="tablist"` with arrow-key navigation (Alpine); each tab may show a `.ha-count`; the selected tab has a 2px `ha-color-primary` underline. Each tab panel is server-rendered and lazy-loaded with `hx-get` on first selection; without JS tabs are anchor links to sections.
- **Field list:** `.ha-dl` two-column grid; labels muted 13px, values strong. IDs in mono with a copy button.
- **Related lists:** a compact DataTable in a card with an "Add" action; empty state "No payments recorded yet." with a small button; loading is skeleton lines with `aria-busy`.
- **Activity timeline:** `.ha-timeline`, newest first, people's names bold, times muted.

**Test ids:** `data-testid="detail-<model>"`, `"tab-<name>"`, `"related-<model>"`, `"related-empty"`.
