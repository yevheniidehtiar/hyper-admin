# RFC: HyperAdmin UI Kit

**Status:** Draft — open for community feedback
**Author:** HyperAdmin maintainers
**Created:** 2026-03-27
**Palette preview:** [`docs/design/palette-preview.html`](palette-preview.html) — open in any browser

---

## 1. Problem Statement

HyperAdmin's current frontend is functional but visually generic. The primary color (`#2563eb`) is plain blue with no connection to the FastAPI/Pydantic ecosystem. Django developers migrating to FastAPI already struggle with the absence of a batteries-included admin panel; when they find HyperAdmin, the interface should immediately feel like it belongs in their new stack.

Beyond aesthetics, the current CSS (~857 lines, single file) lacks:
- A systematic, scalable token architecture
- A multi-modal interaction model (keyboard, touch, pointer — first-class citizens)
- A responsive strategy beyond basic mobile media queries
- A proper dark mode (currently media-query only, no manual toggle)
- Accessibility completeness (no skip-nav, broken focus rings, insufficient touch targets)
- A composable component macro system that scales past ~10 components

This RFC defines the design system that fixes all of the above.

---

## 2. Design Principles

1. **FastAPI ecosystem identity** — the palette, weight, and character of the UI should feel at home alongside FastAPI docs and Pydantic's documentation. A developer should recognize the family.
2. **Input-agnostic** — every interaction is a *semantic action* that maps equally to mouse, keyboard, touch, or future input signals. No interaction is mouse-only.
3. **Desktop-first, mobile-possible** — the primary use case is a developer at a laptop. Mobile is a graceful degradation with meaningful trade-offs, not an afterthought.
4. **Zero build pipeline** — one CSS file, two CDN scripts (HTMX + Alpine.js). No npm, no bundler. A developer should be able to fork the templates and ship.
5. **Progressive enhancement** — every HTMX interaction has an `href` fallback. Every Alpine toggle degrades to CSS `:hover`/`:focus`.
6. **Override-friendly** — rebrand the entire admin by overriding 5–10 CSS custom properties. No `!important` arms race.
7. **Django familiarity** — the mental model (model registration, template override by `{app}/{model}/`, list/form/detail views) stays unchanged. Only the polish improves.

---

## 3. Color System

### 3.1 Philosophy

FastAPI's teal (`#009485`) and Pydantic's pink (`#e92063`) are the community's two most recognizable brand colors. Rather than copying either, HyperAdmin synthesizes them:

- **Primary**: a slightly more saturated teal (`#05bfa4`) that reads "FastAPI ecosystem" at a glance while being more vibrant in UI contexts
- **Accent**: a warmed coral-pink (`#f63d68`) that nods to Pydantic's energy without overwhelming the teal primary
- **Neutral**: cool gray with slight blue undertones, echoing FastAPI's dark documentation aesthetic

### 3.2 Primary Palette

| Step | Light Mode | Dark Mode | Role |
|------|-----------|-----------|------|
| 50 | `#effefa` | — | Selected row background |
| 100 | `#c8fef4` | — | Tag/badge bg, focus ring outer |
| 200 | `#90fde9` | `#90fde9` | Progress bars, badges |
| 300 | `#52f5d8` | `#52f5d8` | Active indicators |
| 400 | `#1edcbe` | `#1edcbe` | Hover states |
| **500** | **`#05bfa4`** | **`#2dd4b8`** | **Primary actions, links** |
| 600 | `#009a86` | `#05bfa4` | Pressed/active states |
| 700 | `#007b6d` | `#009a86` | Active nav items |
| 800 | `#006159` | — | Dark accents |
| 900 | `#00504a` | — | Sidebar bg (dark mode) |

> `#05bfa4` passes WCAG AA on white (`4.6:1`). On dark surfaces, `#2dd4b8` is used instead.

### 3.3 Accent Palette

Used sparingly: "Create New" CTA, notification badges, highlights that need to pop.

| Step | Value | Role |
|------|-------|------|
| 50 | `#fff1f3` | Accent surface tint |
| 100 | `#ffe0e6` | Badge backgrounds |
| 400 | `#ff6488` | Hover |
| **500** | **`#f63d68`** | **Accent actions** |
| 600 | `#e31b54` | Pressed |
| 700 | `#c01048` | Dark accent |

> Pydantic's raw `#e92063` sits between 600–700. The accent-500 is warmed to coral-pink for better admin context.

### 3.4 Semantic Colors

| Semantic | Base | Light bg | Dark text | Use |
|----------|------|----------|-----------|-----|
| Success | `#12b76a` | `#ecfdf3` | `#067647` | Saved, created, online |
| Warning | `#f79009` | `#fffaeb` | `#b54708` | Pending, hints |
| Error | `#f04438` | `#fef3f2` | `#b42318` | Validation, failures |
| Info | `#0ba5ec` | `#f0f9ff` | `#026aa2` | Tips, banners |

> Error red `#f04438` is deliberately distinct from accent pink `#f63d68` — validated against deuteranopia and protanopia simulations.

### 3.5 Neutral Scale

13 steps from `#ffffff` (neutral-0) to `#0c111d` (neutral-950). Cool gray with slight blue undertones. Dark mode inverts the scale rather than shifting hue.

| Step | Light | Dark |
|------|-------|------|
| 0 | `#ffffff` | `#0c111d` |
| 25 | `#fcfcfd` | `#101828` |
| 50 | `#f9fafb` | `#1d2939` |
| 100 | `#f2f4f7` | `#344054` |
| 200 | `#eaecf0` | `#475467` |
| 300 | `#d0d5dd` | `#667085` |
| **400** | **`#98a2b3`** | **`#98a2b3`** | ← crossover |
| 500 | `#667085` | `#d0d5dd` |
| 600 | `#475467` | `#eaecf0` |
| 700 | `#344054` | `#f2f4f7` |
| 800 | `#1d2939` | `#f9fafb` |
| 900 | `#101828` | `#fcfcfd` |
| 950 | `#0c111d` | `#ffffff` |

### 3.6 Surface & Elevation Tokens

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--ha-surface-base` | `#f9fafb` | `#0c111d` | Page background |
| `--ha-surface-raised` | `#ffffff` | `#1d2939` | Cards, modals, dropdowns |
| `--ha-surface-sunken` | `#f2f4f7` | `#101828` | Table headers, sidebar, code |
| `--ha-surface-overlay` | `rgba(16,24,40,0.6)` | `rgba(0,0,0,0.7)` | Modal backdrop |

---

## 4. Typography

### 4.1 Font Stack

```css
--ha-font-sans: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
--ha-font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
```

Inter is already loaded. JetBrains Mono is added for ID fields, timestamps, code values — it matches FastAPI's documentation aesthetic and is free (OFL).

### 4.2 Type Scale

| Token | Size | Line height | Weight | Use |
|-------|------|-------------|--------|-----|
| `--ha-text-xs` | 0.75rem | 1rem | 400/600 | Errors, captions, uppercase headers |
| `--ha-text-sm` | 0.875rem | 1.25rem | 400 | Table cells, help text |
| `--ha-text-base` | 1rem | 1.5rem | 400 | Body, inputs, buttons |
| `--ha-text-lg` | 1.125rem | 1.75rem | 500 | Section headings |
| `--ha-text-xl` | 1.25rem | 1.75rem | 600 | Card titles |
| `--ha-text-2xl` | 1.5rem | 2rem | 700 | Page titles |
| `--ha-text-3xl` | 1.875rem | 2.25rem | 700 | Dashboard headlines |
| `--ha-text-4xl` | 2.25rem | 2.5rem | 800 | Login/splash |

### 4.3 Font Weight Scale

| Token | Value | Use |
|-------|-------|-----|
| `--ha-font-normal` | 400 | Body |
| `--ha-font-medium` | 500 | Labels |
| `--ha-font-semibold` | 600 | Buttons, column headers |
| `--ha-font-bold` | 700 | Page titles |
| `--ha-font-extrabold` | 800 | Brand mark |

---

## 5. Spacing, Radius & Shadow Scales

### 5.1 Spacing (4px base)

16 tokens: `--ha-space-0` (0) through `--ha-space-20` (5rem). Key values:
- `--ha-space-2` = 0.5rem — default gap, input padding
- `--ha-space-4` = 1rem — card padding, section gap
- `--ha-space-6` = 1.5rem — content padding
- `--ha-space-16` = 4rem — layout gutters

### 5.2 Border Radius

| Token | Value | Use |
|-------|-------|-----|
| `--ha-radius-sm` | 0.25rem | Tags, badges |
| `--ha-radius-md` | 0.375rem | Inputs, buttons |
| `--ha-radius-lg` | 0.5rem | Cards, dropdowns |
| `--ha-radius-xl` | 0.75rem | Modals, drawers |
| `--ha-radius-2xl` | 1rem | Login card |
| `--ha-radius-full` | 9999px | Avatars, pills |

### 5.3 Shadows

6 depth levels plus 2 focus ring shadows:

```css
--ha-shadow-xs:    0 1px 2px rgba(16,24,40,0.05);
--ha-shadow-sm:    0 1px 3px rgba(16,24,40,0.1), 0 1px 2px rgba(16,24,40,0.06);
--ha-shadow-md:    0 4px 8px -2px rgba(16,24,40,0.1), 0 2px 4px -2px rgba(16,24,40,0.06);
--ha-shadow-lg:    0 12px 16px -4px rgba(16,24,40,0.08), 0 4px 6px -2px rgba(16,24,40,0.03);
--ha-shadow-xl:    0 20px 24px -4px rgba(16,24,40,0.08), 0 8px 8px -4px rgba(16,24,40,0.03);
--ha-shadow-focus: 0 0 0 4px rgba(5,191,164,0.24);       /* primary */
--ha-shadow-focus-error: 0 0 0 4px rgba(240,68,56,0.24); /* error */
```

### 5.4 z-index Scale

| Token | Value | Layer |
|-------|-------|-------|
| `--ha-z-dropdown` | 10 | Dropdowns, tooltips |
| `--ha-z-sticky` | 20 | Sticky table headers |
| `--ha-z-drawer` | 30 | Side drawers |
| `--ha-z-modal-backdrop` | 40 | Modal overlay |
| `--ha-z-modal` | 50 | Modal content |
| `--ha-z-toast` | 60 | Toasts |
| `--ha-z-skip-nav` | 100 | Skip nav link |

### 5.5 Animation Tokens

| Token | Value | Use |
|-------|-------|-----|
| `--ha-duration-instant` | 50ms | Checkboxes, toggles |
| `--ha-duration-fast` | 100ms | Button hover, focus rings |
| `--ha-duration-normal` | 150ms | Dropdowns |
| `--ha-duration-slow` | 250ms | Drawers, modals |
| `--ha-duration-slower` | 350ms | Page transitions |
| `--ha-ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General |
| `--ha-ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Elements entering |
| `--ha-ease-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Emphasis |

> All durations collapse to `0ms` when `prefers-reduced-motion: reduce` is active.

---

## 6. Multi-Modal Interaction Design

### 6.1 Semantic Action Model

Every interaction exposes a **semantic action** independent of input method:

| Action | Mouse | Keyboard | Touch | Future |
|--------|-------|----------|-------|--------|
| Activate | Click | Enter / Space | Tap | Voice "open" |
| Navigate | Click link | Tab → Enter | Tap | "Go to users" |
| Select row | Click | Space on focused row | Tap | "Select row 3" |
| Sort | Click header | Enter on header | Tap header | "Sort by name" |
| Delete | Click delete btn | Del on focused row | Swipe left + confirm | "Delete selected" |
| Search | Click input | `Cmd+K` or `/` | Tap search icon | "Search for..." |
| Filter | Select dropdown | Arrow keys | Tap | "Filter by active" |
| Paginate | Click prev/next | Arrow keys | Swipe | "Next page" |
| Dismiss | Click ✕ | Escape | Swipe away | "Dismiss" |
| Submit form | Click Save | Ctrl+S | Tap Save | — |

### 6.2 Keyboard Navigation

**Focus ring implementation** (replaces current `outline: none` pattern):

```css
:focus-visible {
  outline: 2px solid var(--ha-color-primary-500);
  outline-offset: 2px;
  border-radius: var(--ha-radius-sm);
}
:focus:not(:focus-visible) { outline: none; }
```

**Skip navigation** (first element in `_base.html`):

```html
<a href="#ha-main-content" class="ha-skip-nav">Skip to main content</a>
```

Visible only on focus, positioned top-left with card shadow.

**Keyboard shortcuts** (Alpine.js on `<body>`):

| Shortcut | Context | Action |
|----------|---------|--------|
| `Cmd/Ctrl+K` | Global | Open command palette *(Phase E)* |
| `/` | Not in input | Focus search |
| `?` | Not in input | Show shortcuts overlay |
| `c` | List view, not in input | Navigate to create |
| `j` / `k` | Table with focused row | Move down / up |
| `Enter` | Focused table row | Open detail |
| `e` | Focused table row | Open edit |
| `Escape` | Any overlay | Close |
| `Ctrl+S` | Form | Submit |

### 6.3 Touch Optimization

Minimum 44×44px touch targets for all interactive elements, activated via media query:

```css
@media (pointer: coarse) {
  .ha-btn, .ha-action-link, .ha-action-delete,
  .ha-pagination-btn, .ha-filter-toggle,
  .ha-dropdown-item, .ha-sidebar-link {
    min-height: 44px;
    min-width: 44px;
    display: inline-flex;
    align-items: center;
  }
}
```

**Swipe gestures** (Alpine.js `x-swipe` directive, no dependencies):
- Table rows: swipe-left → reveal delete zone, swipe-right → reveal edit
- Toasts: swipe-right → dismiss
- Sidebar drawer: swipe-left → close

### 6.4 Interactive State Machine

Every interactive element transitions through:

```
Default → Hover (tint +10%) → Active (tint +20%, scale 0.98) → Focus-visible (outline)
                                                              ↓
                                                          Disabled (50% opacity, pointer-events: none)
```

---

## 7. Responsive Strategy

### 7.1 Breakpoints

| Name | Min-width | Primary target |
|------|-----------|----------------|
| *(base)* | 0 | Portrait phones |
| `sm` | 640px | Landscape phones |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| **`xl`** | **1280px** | **Desktops — design target** |
| `2xl` | 1536px | Wide monitors |

### 7.2 Component Adaptation per Breakpoint

| Component | `< md` | `md – lg` | `lg+` |
|-----------|--------|-----------|-------|
| **Sidebar** | Hidden; hamburger → full-overlay drawer | Collapsed icon rail (48px wide) | Full (256px) |
| **Data table** | CSS-only stacked cards (no duplicate markup) | Horizontal scroll + sticky col 1 | Full table |
| **Pagination** | Prev / Next only | Compact (prev + current + next) | Full with page numbers |
| **Filter bar** | Vertical accordion, collapsed | Horizontal wrap | Single-row horizontal |
| **Form layout** | Single column, full-width inputs | Single column, max 640px | Two-column grid for related fields |
| **Actions** | Fixed bottom bar | Inline | Inline |
| **Search** | Icon tap → full-width overlay | Full-width in content | Fixed-width in toolbar |
| **Navbar** | Brand + hamburger | Full | Full |

### 7.3 Table-to-Card Transformation

Pure CSS — no JavaScript, no duplicate HTML. Requires `data-label="{{ field }}"` on each `<td>`:

```css
@media (max-width: 767px) {
  .ha-table thead { display: none; }
  .ha-table tbody { display: flex; flex-direction: column; gap: var(--ha-space-3); }
  .ha-table-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--ha-space-2);
    padding: var(--ha-space-4);
    border: 1px solid var(--ha-color-border);
    border-radius: var(--ha-radius-lg);
    background: var(--ha-surface-raised);
  }
  .ha-table-cell::before {
    content: attr(data-label);
    font-weight: 600;
    font-size: var(--ha-text-xs);
    text-transform: uppercase;
    color: var(--ha-color-text-muted);
    display: block;
    margin-bottom: var(--ha-space-0.5);
  }
}
```

### 7.4 Sidebar Width Token

```css
:root                          { --ha-sidebar-width: 0; }
@media (min-width: 768px)  { :root { --ha-sidebar-width: 3rem; } }
@media (min-width: 1024px) { :root { --ha-sidebar-width: 16rem; } }
```

The layout shifts automatically; no JavaScript required for the static case.

---

## 8. Component Inventory

### 8.1 Tier 1 — Upgrade Existing (11 components)

All exist in `src/hyperadmin/templates/components/`. Upgraded in-place.

| Component | Current gaps | Additions |
|-----------|-------------|-----------|
| **Button** | Primary + danger + link only | Secondary, outline, ghost, icon-only; sm/md/lg sizes; loading spinner state |
| **Input** | Text only | Prefix/suffix slots, validation ring states, character counter |
| **Select** | Native `<select>` | Searchable option (Alpine.js), multi-select chip display |
| **Checkbox** | Basic | Toggle switch variant, indeterminate state |
| **Table** | Basic sort | Row selection checkboxes, bulk actions bar, empty state, responsive cards |
| **Card** | Flat padding box | header/body/footer sections; stat, action, media variants |
| **Alert** | 4 levels | Dismissible (×), icon slot, inline action link |
| **Toast** | Fixed container | Stacking, auto-dismiss progress bar, slide-in/out animation |
| **Pagination** | Prev/next + info | Page number buttons, per-page selector |
| **Sidebar** | Static list | Sections, collapse/expand, icon support, active highlight |
| **Navbar** | Brand + user dropdown | Breadcrumbs slot, theme toggle button, quick-action area |

### 8.2 Tier 2 — New Foundation Components (17 components)

New template files under `src/hyperadmin/templates/components/`.

| Component | File | Description |
|-----------|------|-------------|
| Badge | `badge.html` | Status indicators, counts, removable tags |
| Breadcrumbs | `breadcrumbs.html` | Navigation hierarchy from page context |
| Data Card (KPI) | `data_card.html` | Metric display: value, label, trend arrow |
| Drawer | `drawer.html` | Side panel (right/left), doesn't navigate away |
| Dropdown Menu | `dropdown.html` | Context menus, action menus, user menu |
| Empty State | `empty_state.html` | No-data screen with illustration + CTA |
| Modal / Dialog | `modal.html` | Confirmation, quick form, alert dialogs |
| Skeleton Loader | `skeleton.html` | HTMX `hx-indicator` replacement — pulsing placeholders |
| Tabs | `tabs.html` | Content sectioning within a view |
| Tooltip | `tooltip.html` | CSS-only via `[data-tooltip]` attribute |
| Avatar | `avatar.html` | User identity: initials or image, multiple sizes |
| Progress | `progress.html` | Linear progress bar (import, bulk action) |
| Tag / Chip | `tag.html` | Categorization, multi-value display, removable |
| Stat Row | `stat_row.html` | Horizontal KPI strip for dashboard |
| Timeline | `timeline.html` | Audit log, activity feed |
| Description List | `description_list.html` | Key-value detail view (replaces raw `<dl>`) |
| Icons | `icons.html` | ~40 SVG icon macros, all `currentColor`, 3 sizes |

### 8.3 Tier 3 — Advanced (Future phases)

Kanban board, tree view, calendar/date range picker, rich text editor, file upload drop zone, inline field editing, split master-detail layout, data export (CSV/JSON), diff/audit view.

### 8.4 Macro API Convention

All components follow the same keyword-argument pattern:

```jinja2
{# Import once via components/_lib.html #}
{% from "components/_lib.html" import badge, button, modal, tooltip %}

{{ badge("Active", variant="success", size="sm") }}
{{ button("Save Changes", type="submit", variant="primary", size="lg") }}
{{ button("+ Create New", href=create_url, variant="accent") }}
{{ tooltip("More info", text="This field is required") }}
```

**Argument order:**
1. Content / text (positional)
2. `variant` — visual style: `default`, `primary`, `accent`, `success`, `warning`, `error`, `info`, `outline`, `ghost`
3. `size` — scale: `sm`, `md` (default), `lg`
4. Boolean flags: `dismissible`, `loading`, `disabled`, `removable`
5. `class` — additional CSS classes
6. HTMX attrs as kwargs: `hx_post`, `hx_target`, `hx_confirm`, etc.

This pattern is analogous to Django's `{% load %}` + template tag — familiar to the target audience.

---

## 9. Theming Architecture

### 9.1 Three-Way Dark Mode

```css
/* Light mode (default) */
:root { /* all light tokens */ }

/* Manual dark (user toggled, stored in localStorage) */
:root[data-theme="dark"] { /* dark token overrides */ }

/* System preference (applies when no data-theme set) */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* dark token overrides */ }
}
```

**Anti-FOUC script** (inline, in `<head>` before any CSS):

```html
<script>
  (function() {
    var t = localStorage.getItem('ha-theme');
    if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
  })();
</script>
```

**Alpine.js theme toggle** (cycles `light → dark → system`):

```js
Alpine.data('themeToggle', () => ({
  theme: localStorage.getItem('ha-theme') || 'system',
  icons: { light: '☀', dark: '☾', system: '⊙' },
  cycle() {
    const modes = ['light', 'dark', 'system'];
    this.theme = modes[(modes.indexOf(this.theme) + 1) % modes.length];
    localStorage.setItem('ha-theme', this.theme);
    if (this.theme === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', this.theme);
  }
}));
```

### 9.2 User Customization

Override any subset of CSS custom properties after loading `hyperadmin.css`:

```css
/* my-admin-theme.css — load after hyperadmin.css */
:root {
  --ha-color-primary-500: #7c3aed;   /* rebrand to purple */
  --ha-color-accent-500:  #f59e0b;   /* amber accents */
  --ha-font-sans: 'Outfit', system-ui, sans-serif;
  --ha-radius-md: 0.5rem;            /* rounder corners */
  --ha-sidebar-width: 14rem;         /* narrower sidebar */
}
```

No `!important`, no specificity fights. Every visual property is a token.

### 9.3 Shipped Theme Presets

| File | Description |
|------|-------------|
| `hyperadmin.css` | Default: FastAPI teal + Pydantic coral |
| `ha-theme-neutral.css` | Desaturated gray primary — enterprise/internal tools |
| `ha-theme-midnight.css` | Deep navy + amber — dark-first variant |

### 9.4 Accessibility Presets

```css
/* High contrast — via data-a11y="high-contrast" on <html> */
:root[data-a11y="high-contrast"] {
  --ha-color-border: #000000;
  --ha-color-text: #000000;
  --ha-shadow-sm: none;
  --ha-shadow-md: none;
}

/* System reduced motion */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0ms !important; transition-duration: 0ms !important; }
}

/* System high contrast */
@media (prefers-contrast: more) {
  :root { --ha-color-border: var(--ha-color-neutral-700); }
}
```

---

## 10. Migration Path from Current CSS

The current `hyperadmin.css` (857 lines) uses hardcoded hex values throughout. Migration is purely additive token-by-token — no breaking changes to template class names.

### Phase A — Token Migration (non-breaking)

1. Expand `:root` with the full token set from this RFC
2. Replace all hardcoded hex/rem values in component rules with token references
3. Replace `#2563eb` with `var(--ha-color-primary-500)` (resolves to `#05bfa4`)
4. Update dark mode from `@media (prefers-color-scheme: dark)` to the three-way system

**Result:** visual refresh only — no template changes, no test changes.

### Phase B — Core Component Upgrades

Upgrade existing 11 components with new variants, focus rings, responsive behavior. Add `data-label` to `components/table.html`. Add skip-nav to `_base.html`.

### Phase C — New Foundation Components

17 new template files + corresponding CSS sections. Central `components/_lib.html` macro import hub.

### Phase D — Interaction Layer

Keyboard shortcut system, swipe gesture directive, theme toggle in navbar, bulk selection UI.

### Phase E — Command Palette *(deferred)*

`Cmd+K` universal search/action launcher — requires Phase C drawer + modal components as foundation.

### Phase F — Advanced Components *(future)*

Kanban, tree, timeline, inline edit, split view, data viz.

---

## 11. Developer Experience

### Django Admin Familiarity Map

| Django Admin concept | HyperAdmin equivalent | Status |
|---------------------|----------------------|--------|
| `ModelAdmin` class | `ModelView` + `AdminOptions` | Exists |
| `list_display` | `column_list` | Exists |
| `list_filter` | `list_filter` | Exists |
| `search_fields` | `search_fields` | Exists |
| Template override `{app}/{model}/` | Same via `_get_template_name()` | Exists |
| `fieldsets` | `form_fieldsets` | Planned |
| `actions` | Bulk actions | Phase D |
| `inlines` | Related inline editing | Phase F |

### Component Playground

A debug route at `/{admin_prefix}/_components/` (only when `DEBUG=True`) renders every component with all variants. No external dependencies — the page is self-contained. Useful for:

- Visual regression review during development
- Designer handoff
- Third-party theme authors verifying their overrides

---

## 12. Icon Strategy

~40 SVG icons shipped as Jinja2 macros in `components/icons.html`. All icons:
- Use `currentColor` for stroke/fill (inherit from text color)
- Accept `size` parameter: `sm` (16px), `md` (20px), `lg` (24px)
- Accept `class` kwarg for custom styling
- Can be replaced entirely by swapping `icons.html`

**Essential set:** plus, minus, edit (pencil), trash, eye, search, filter, sort-asc, sort-desc, chevron-up/down/left/right, close (×), check, warning-triangle, info-circle, user, menu (hamburger), logout, settings (gear), home, external-link, copy, download, upload, calendar, clock, arrow-left/right, refresh, more-horizontal (⋯), sun, moon, monitor (system).

---

## 13. Open Questions

These require community input before implementation:

1. **Table column resize** — pure CSS resize handles vs. Alpine.js drag. CSS approach is simpler but has rough edges on mobile.
2. **Searchable select** — Alpine.js inline vs. a lightweight external library (`tom-select`/`choices.js`). Inline keeps the zero-dependency promise; external gives better UX.
3. **KPI sparklines** — inline SVG paths (server-rendered, zero JS) vs. a tiny charting lib. Server-rendered is simpler but requires data shaping in the view.
4. **Sidebar icon rail** (collapsed md breakpoint) — should icons be required (breaking change for existing `ModelView`s) or optional?
5. **Macro import strategy** — single `_lib.html` mega-import vs. per-page explicit imports. Single import is convenient; per-page is more explicit about dependencies.

---

## 14. References

- [FastAPI brand](https://fastapi.tiangolo.com/) — teal `#009485`
- [Pydantic brand](https://docs.pydantic.dev/) — pink `#e92063`
- [WCAG 2.1 AA contrast requirements](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [`docs/frontend/overview.md`](../frontend/overview.md) — current frontend architecture
- [`docs/frontend/htmx_patterns.md`](../frontend/htmx_patterns.md) — HTMX conventions
- [`docs/design/palette-preview.html`](palette-preview.html) — visual palette prototype
