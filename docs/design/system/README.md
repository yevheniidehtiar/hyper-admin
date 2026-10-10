HyperAdmin is the open-source admin you add to an existing FastAPI app in ten minutes without it taking over. This system is its look: calm, precise, fast. A back office that people trust with money and customer data for eight hours a day. Data gets the space and the contrast; chrome stays quiet; one bright violet accent appears rarely.

Everything here ships as **CSS custom properties (`--ha-*`) plus Jinja2 markup**. No build step, no npm, no client framework. The component previews are the HTML the templates should emit; `components/bundle.css` is the stylesheet those templates use.

## Rules that every screen follows

1. **Guest in someone else's app.** Every selector starts at an `ha-` class or sits under `.ha-root`. Never style a bare element globally. A host rebrands by overriding the tokens in [Rebrand your admin](#rebrand-your-admin), not by editing CSS.
2. **No build pipeline.** One CSS bundle, server-rendered HTML, HTMX and Alpine.js. Charts are SVG emitted by Jinja2 macros. A template is forked and shipped, nothing is compiled.
3. **Data first, chrome second.** Tables, forms and numbers get `ha-color-text-strong` and the most space. Navigation, borders and decoration use `ha-color-text-muted`, `ha-color-border` and stay low-contrast.
4. **Input-agnostic.** Every action works with mouse, keyboard and touch. Nothing is hover-only: tooltips also open on focus and tap; row actions are visible buttons, not hover reveals. Every HTMX interaction has a plain `<a href>` or `<form>` fallback.
5. **Accessible by default.** WCAG 2.2 AA in light and dark. Visible focus everywhere. Targets at least `ha-target-min` (24px), `ha-target-touch` (44px) under `(pointer: coarse)`. `prefers-reduced-motion` turns motion off.
6. **World-wide by default.** Logical properties only (`margin-inline-start`, `inset-inline-end`, `border-block-end`), so `dir="rtl"` mirrors the layout with no second design.
7. **Familiar mental model.** List, detail, create and edit keep the Django-admin shape. The polish is new, the shape is not.
8. **Markup is a contract.** Tests select by role, accessible name and `data-testid`, never by `ha-*` class. Each component's guidelines list its `data-testid` and accessible name.

## Voice and content

- **Sentence case** everywhere: buttons, headings, nav, column headers. "Add invoice", not "Add Invoice" or "ADD INVOICE".
- **Verb first on actions**, naming the object and, for destructive ones, the count: "Delete 3 invoices", "Mark as paid", "Save and continue editing".
- **Plain and specific errors** that say what is wrong and how to fix it: "Amount must be greater than 0." Not "Invalid input".
- **Name people in realtime copy**: "Bram changed this invoice", "Bram is editing".
- **No emoji, no exclamation marks, no "Oops".** The 500 page says "Something went wrong on our side" and gives a reference ID.
- **"You" for the reader**, never "we" for HyperAdmin inside someone else's product: the admin speaks for the host app.
- **Data is data**: dates, numbers, currencies and time zones come from the locale and `settings.timezone`. Never hard-code "MM/DD", "$" or a decimal point in a template or a mock-up.
- Labels must survive **30–40 % expansion** (German, Russian). Buttons and nav items wrap; table headers and long cells truncate with a `title` tooltip (`.ha-trunc`). Nothing clips. No text inside images.

## Colour

Two themes, `light` and `dark`, selected by `HyperAdminSettings(theme="auto" | "light" | "dark")` and the navbar toggle (`data-theme` on `<html>`). Every text token's note names the grounds it is checked on.

- **Surfaces.** `ha-surface-base` is the page; `ha-surface-raised` holds data (tables, cards, inputs, navbar); `ha-surface-sunken` is the table header, the filter bar and skeletons; `ha-surface-overlay` is for dialogs, menus and toasts. Separate surfaces with `ha-color-border` hairlines, not shadows.
- **Text.** `ha-color-text-strong` for headings, record titles and totals; `ha-color-text` for body and ordinary cells; `ha-color-text-muted` for help text, headers and metadata. Never put muted text on `ha-color-primary-soft` or any status tint.
- **Brand teal.** `ha-color-brand` (#0D9488 / #2DD4BF) is the identity: the logo tile, the focus ring, the active-nav bar, chart series 1. In light it is **not** a text colour and **not** a fill under white text (3.74:1). Fills that carry a label use `ha-color-primary` with `ha-color-on-primary`; teal text uses `ha-color-primary-text`.
- **Hyper violet.** `ha-color-accent` at most once per screen: one accent CTA ("Ask the data"), the "New" tag, someone-else-is-editing. Never for anything destructive. This replaces the borrowed Pydantic coral, which sat next to the error red.
- **Status** uses the `-text` token on its `-soft` tint: success (Paid), warning (Overdue), info (Draft, reconnecting), danger (Failed, errors). A status is never colour alone: pills carry a word, alerts an icon and a title, deltas an arrow.
- **Danger buttons** use `ha-color-danger` with `ha-color-on-danger`, and only for the confirming action of a destructive flow. The button that opens the confirm dialog can be secondary with a trash icon.
- **Charts** use `ha-chart-1` … `ha-chart-6` in order, plus `ha-chart-grid` and `ha-chart-axis`. The six steps alternate lighter and darker, so neighbouring series differ in lightness (at least 1.5:1 between neighbours in both themes) as well as hue, and each holds 3:1 against `ha-surface-raised`. A second line series is also dashed. Direct labels on a series use a text colour, not the series colour (`ha-chart-1` is 3.74:1, too light for 12px text).
- **Focus ring.** `outline: 2px solid var(--ha-color-focus-ring); outline-offset: 2px` on every interactive element, already in `bundle.css` via `:focus-visible`. Inputs draw it at offset 0 and colour their border with it.

Values tuned from the brief, so contrast holds: light `ha-color-primary` is #0F766E (white label 5.47:1); `ha-color-text-muted` is #5D6A7E (5.20:1 on base); `ha-color-danger-text` is #C8291D (5.10:1 on its tint); `ha-color-border-strong` is #7D8799 (3.43:1 on base, for control edges).

## Type

- **Inter** (self-hosted, `fonts/InterVariable.woff2`, 94 KB) for Latin, Cyrillic and Greek; never load it from Google Fonts. `font-family: var(--font-sans)`. It is Inter 4 pinned to its 14pt optical size with a 400–600 weight axis: the only weights the system uses are 400, 500 and 600.
- **JetBrains Mono** (`fonts/JetBrainsMonoVariable.woff2`, 44 KB, weights 400–500) via `var(--font-mono)` for IDs, UUID and string keys, API keys, ISO timestamps. Always `dir="ltr"` / `.ha-mono`, which isolates it inside RTL text.
- Other scripts fall through the stack: Noto Sans Arabic, Hebrew, Devanagari, Thai, SC, JP, KR, then `system-ui`. For Japanese and Korean pages, put Noto Sans JP or KR before SC with a `:lang(ja)` / `:lang(ko)` override so Han glyphs take the right regional forms.
- **14px is the base** for tables and forms (`ha-body`, 21px line, 1.5). Line height never drops below 1.5 for body text: Thai and Devanagari marks need it. Use `ha-label` (13px/500) for field labels and column headers, `ha-caption` (12px) for help text and pills. Nothing smaller than 12px.
- Headings: `ha-h1` page title, `ha-h2` record summary, `ha-h3` panel and dialog titles, `ha-h4` card and chart titles. `ha-display` is reserved for one hero number.
- **Numbers**: `.ha-num` (or `font-variant-numeric: tabular-nums` and `text-align: end`) in every numeric column, total and numeric input. Negative money uses a real minus sign (−) and `ha-color-danger-text`, never parentheses alone.
- No `text-transform: uppercase`: it breaks for scripts without case and shouts in a back office.

## Space, size, density

- 4px grid: `ha-space-1` … `ha-space-16`. Card padding `ha-space-6` (comfortable) or `ha-space-4` (compact); page gutter `ha-space-6`, `ha-space-4` under `ha-bp-md`.
- **Two densities.** Comfortable is the default: `ha-row-height` 44px, `ha-control-height` 36px. `data-density="compact"` on `<html>` or any container switches to `ha-row-height-compact` 32px and `ha-control-height-compact` 28px. Under `(pointer: coarse)` rows and controls grow to `ha-target-touch` whatever the density.
- Layout: `ha-navbar-height` 56px; sidebar `ha-sidebar-width` 256px, `ha-sidebar-width-collapsed` 64px; content up to `ha-content-max`. Breakpoints: below `ha-bp-md` (768px) tables become cards and the sidebar a drawer; below `ha-bp-lg` the sidebar starts collapsed. Design target is 1280–1920px; everything must work at 375px and at 200 % zoom without horizontal page scroll.

## Shape and elevation

- Radii: `ha-radius-sm` checkboxes and cells being edited; `ha-radius-md` buttons, inputs, chips, nav items; `ha-radius-lg` cards, tables, alerts, toasts; `ha-radius-xl` dialogs and the login card only; `ha-radius-pill` pills, avatars, counts.
- Shadows are few: `ha-shadow-sm` on cards and the table on the page background, `ha-shadow-md` on menus and popovers, `ha-shadow-lg` on dialogs, toasts and the drawer. Borders do the separating; shadows only say "floating".
- No gradients. No coloured left-border cards. The only coloured edge is the 3px active-nav indicator (`ha-color-brand`) and the error edge of a formset row.

## Motion

100–250ms, only to explain a change: a row swapped in by HTMX (fade 150ms), a panel or drawer opening (200ms ease-out), a toast arriving (slide 200ms). Never loop anything but a spinner or skeleton pulse. `bundle.css` removes all animation and transition under `prefers-reduced-motion: reduce`.

## Iconography

- **Lucide** (ISC licence), outline, 24px grid drawn at `ha-icon-size` 20px with a **1.5px stroke**; 16px (`.ha-icon--sm`) inside pills, chips and compact buttons.
- Inline SVG with `class="ha-icon"` and `stroke="currentColor"` so icons take the text colour. No icon font, no sprite request.
- Decorative icons get `aria-hidden="true"`. An icon-only button gets an `aria-label` that names the action and the object: "Edit invoice INV-0142".
- **Mirroring in RTL**: add `.ha-icon--mirror` to directional icons (chevrons, back and forward arrows, progress, "reply"). Never mirror checkmarks, media controls, clocks, charts' up/down deltas, sort arrows, or the logo.
- `src/hyperadmin/static/icons/` holds the 25 icons the components use (`stroke="currentColor"`); add more from the same pinned Lucide release.

## Logo

The mark is an **"H" built from table rows**: two cells, a full-width row, two cells, knocked out of a rounded tile. It reads at 16px, works in one colour and is not related to any other project's logo.

- `hyperadmin-mark.svg`: full colour, teal tile with white rows. Sidebar, login, docs.
- `hyperadmin-mark-mono.svg`: one ink (#0B1220) with the rows cut out; recolour the fill for print or dark grounds.
- `hyperadmin-favicon.svg`: cut-out mark in #0D9488: 3:1 or better on white and on typical dark tabs, 2.9:1 on a grey inactive tab. The asset store strips `<style>`, so the stored file has no dark-mode switch; the repository copy in `src/hyperadmin/static/img/` adds `@media (prefers-color-scheme: dark) { path { fill: #2DD4BF } }`.
- `hyperadmin-wordmark.svg` / `-dark.svg`: mark plus "**Hyper**Admin" in Inter SemiBold + Regular, outlined.
- Clear space: one row height (a sixth of the mark) on every side. Minimum size 16px for the mark, 96px wide for the wordmark. Never recolour the rows, add effects, or set the word in another face.
- Inside a host app the navbar shows the **host's** `site_title` next to the mark; the wordmark is for HyperAdmin's own docs, demo and README.

## Charts

Server-rendered SVG first: a Jinja2 macro emits the `<svg>`, themed by tokens, swapped by HTMX, printable, with no JavaScript. The rules for the macros:

- Aggregate in the database, thin to at most the chart's width in points (LTTB), draw **one `<path>` per line series**, keep per-point elements only for bars and tooltips.
- `viewBox` with `width: 100%`; below `ha-bp-md` a chart may fall back to its stat card or its table.
- Every chart has a `<title>` and a `<desc>` that states the takeaway, a legend or direct labels with text, and a `<details>` "Show as table" fallback under it.
- A chart without focusable points (sparkline, static export) is `role="img"`. A chart with tooltips is `role="group"` with `aria-labelledby` (title) and `aria-describedby` (desc): `role="img"` would hide its focusable points from screen readers.
- Tooltips are `<g>` groups with a focusable hit area (`tabindex="0"`, `role="img"` and an `aria-label` holding the values) so they open on hover, focus and tap.
- The plot keeps `direction: ltr` inside RTL pages (`.ha-chart` sets it), so `text-anchor` and the time axis never flip.
- Data inside the plot stays left-to-right in RTL; the frame (title, legend, period switch) mirrors. Tick labels and tooltips use locale number, date and currency formats.
- The optional client-side layer (`interactive=True`) is vendored, pinned, loaded only on that report page, and the SVG still renders without it.

## Rebrand your admin

A host app restyles HyperAdmin by overriding a handful of tokens after `hyperadmin.css`, scoped to the admin's root:

```css
/* in a stylesheet loaded after hyperadmin.css; set on the same elements tokens.css uses, so aliases such as
   --ha-color-focus-ring: var(--ha-color-brand) pick up the new value (a var() resolves where it is declared) */
:root, [data-theme="light"] {
  --ha-color-brand: #1F5FBF;          /* identity colour: focus ring, active nav, chart 1 */
  --ha-color-primary: #1A4F9E;        /* primary button fill: must hold 4.5:1 with on-primary */
  --ha-color-primary-hover: #153F7E;
  --ha-color-primary-text: #1A4F9E;   /* links: 4.5:1 on surface-base */
  --ha-color-primary-soft: #EEF4FC;   /* active nav and chip tint */
  --ha-color-accent: #8A3FFC;         /* or set it equal to primary for a single-colour brand */
  --ha-radius-md: 4px;                /* squarer controls */
  --font-sans: "Your Sans", system-ui, sans-serif;
}
[data-theme="dark"] { --ha-color-brand: #7FB0F5; --ha-color-primary: #7FB0F5; --ha-color-on-primary: #0B1220; /* … */ }
```

Override both themes, keep each pair at its stated contrast, and leave the neutral, status and chart tokens alone unless the brand requires it. `HyperAdminSettings(site_title=...)` replaces the name in the navbar and login.

## In this repository

| Design system | Repository |
|---|---|
| `tokens.json` (source of truth) | `src/hyperadmin/static/css/_tokens.css` (light) and `_dark-mode.css` (dark), value for value |
| `components/bundle.css`, `components/*/preview.html` | the reference; ported into the shipped partials (`_buttons.css`, `_table.css`, `_forms.css`, `_navbar.css`, `_sidebar.css`, …) under their existing class names (`.ha-btn-primary`, `.ha-table-cell`, `.ha-sidebar-link`, …), so forked host templates keep working. `.ha-btn--primary` and the other button modifiers are aliases |
| fonts | `src/hyperadmin/static/fonts/` (WOFF2 + OFL licences), loaded by `_fonts.css`; Inter is preloaded by `_base.html` |
| logo, favicon | `src/hyperadmin/static/img/`; the navbar and login show the mark next to `site_title` |
| icons | `src/hyperadmin/static/icons/`, inlined by the `icon(name)` macro in `templates/components/_icons.html` (generated: `uv run python scripts/generate_icon_macro.py`). A `ModelAdmin.icon` or nav item `icon` that names one of them renders the Lucide icon |
| HTMX, Alpine.js | vendored at exact versions in `src/hyperadmin/static/js/vendor/` (no CDN request) |

Name mapping, where the shipped CSS keeps an older name:

| Design-system token | Shipped name |
|---|---|
| `ha-color-*-soft` | `--ha-color-*-light` (both names are defined) |
| `ha-color-border` (hairline) | `--ha-color-border-light` |
| `ha-color-border-strong` (control edge) | `--ha-color-border-strong`, and `--ha-color-border` points to it |
| `ha-radius-pill` | `--ha-radius-pill` = `--ha-radius-full` |
| `ha-shadow-lg` (dialogs, toasts) | `--ha-shadow-xl` |
| `--font-sans`, `--font-mono` | `--ha-font-family`, `--ha-font-mono` |
| primary scale | partials use steps by role: 50 tint, 400 brand, 500 action fill, 600 action hover, 700/800 teal text |

- Theme: the app sets `.ha-theme-dark` / `.ha-theme-light` on `<html>` (and `data-theme` works too); "auto" follows `prefers-color-scheme` in `_dark-mode.css`. `bundle.css` keys its few theme-specific rules off `[data-theme="dark"]`; when it is ported, add `.ha-theme-dark` to those selectors.
- Open the previews in a browser: `docs/design/system/index.html` (no server needed; `?theme=dark` and `?dir=rtl` work on each preview).
- Changing a value: edit `tokens.json`, mirror it in `_tokens.css` / `_dark-mode.css`, regenerate `tokens.css` here, and refresh the visual baselines. Render them on Linux, as CI does, for example in `mcr.microsoft.com/playwright/python:v<playwright version>-noble` with `RESPONSIVE_SNAPSHOTS_UPDATE=1 uv run pytest tests/e2e/test_visual_regression.py tests/e2e/test_i18n.py`; macOS renders differ by more than the threshold.
- Cascade layers: the focus ring and the base `.ha-icon` rule sit in the `reset` layer on purpose, so a component (an input, an icon inside a row action) can adjust them. Later layers win whatever the specificity.

## Implementing the rest

- The table's card layout is still a viewport media query at `ha-bp-md`. Moving it to a container query on the table wrapper (`container: ha-table / inline-size`) lets a table in a narrow panel or dialog turn into cards too.
- Components the templates do not emit yet: status pills (enum columns still print `Status.PAID`), stat cards, charts, dialogs (deletes still use `hx-confirm`), breadcrumbs, presence avatars, the density switch and the collapsed sidebar. Their CSS is in `components/bundle.css`.
- First load stays under 150 KB of CSS, fonts and JS: split each font into a Latin and a Cyrillic+Greek file with `unicode-range`, so a Latin-script page downloads only the Latin halves.
- Copy still to bring to sentence case: "Create New Invoice" and "Invoice List" should read "Add invoice" and "Invoices"; that changes translation message IDs, so it goes with a catalogue update.
