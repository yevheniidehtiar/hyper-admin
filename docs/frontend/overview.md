# Frontend Overview

HyperAdmin's frontend is built on three complementary technologies — **HTMX**, **Alpine.js**, and **plain CSS** — with everything rendered server-side by Jinja2. There are no JavaScript frameworks, no build pipelines for the UI, and no third-party widget libraries.

## Design Philosophy

**Server is the source of truth.** Every piece of HTML — including form fields, error messages, paginated tables, and option lists — is rendered by the server. The browser receives HTML, not JSON. This keeps client-side logic minimal and the system auditable.

**Progressive enhancement.** Forms and links work without JavaScript. HTMX layers partial-page updates on top. Alpine.js handles the handful of interactions that are purely local (dropdown toggles, toast dismiss timers).

**Atomic CSS, no build step.** Styling uses modular CSS partials imported via `@layer` from a single entry file (`hyperadmin.css`). CSS custom properties provide the design token layer. There is no Tailwind, Bootstrap, or Sass compilation. Deployment is `uv run fastapi dev` and nothing else.

---

## Stack

| Layer | Technology | Responsibility |
|---|---|---|
| Templates | Jinja2 | Server-side HTML rendering |
| Server interactions | HTMX 1.9 | Partial-page updates, form submission, search, pagination |
| Client-side behaviour | Alpine.js 3 | Dropdowns, modals, focus traps |
| Styling | Custom CSS (`ha-*`) | Design tokens, layout, components |
| Forms | Pydantic v2 | Validation, error collection |

---

## Template Hierarchy

Templates use three-level inheritance:

```
_base.html                   ← HTML shell: head, HTMX/Alpine scripts, CSS link
├── list_layout.html         ← list page frame (navbar, sidebar, search bar, table)
│   └── (rendered by list view per model)
├── form_layout.html         ← form page frame (card wrapper, default form_body block)
│   ├── create.html          ← sets hx-post, "Create" button
│   └── update.html          ← sets hx-put, "Update" button
└── detail_layout.html       ← read-only field display
    └── detail.html
```

Partials are included into `_base.html`:

- `_navbar.html` — top navigation with Alpine.js user menu dropdown
- `_sidebar.html` — left nav with registered model links
- `_messages.html` — toast container (Alpine.js, auto-dismiss after 5 s)

Components are reusable snippets called from layout templates:

- `components/table.html` — data table with HTMX sortable headers
- `components/search_input.html` — search-as-you-type with HTMX
- `components/pagination.html` — page controls with HTMX links
- `components/filter_bar.html` — filter dropdown bar with HTMX
- `components/sortable_header.html` — sortable column header with HTMX
- `components/fieldset.html` — collapsible fieldset group with Alpine.js
- `components/_macros.html` — central macro library (see below)

### Macro Library (`components/_macros.html`)

The `_macros.html` file provides reusable Jinja2 macros that eliminate boilerplate across widget templates:

- **`field_wrapper(field)`** — wraps any form field with the standard `ha-form-group` div, label, help text, and error list. Used via the Jinja2 `{% raw %}{% call %}{% endraw %}` pattern:

{% raw %}
```jinja2
{%- from "components/_macros.html" import field_wrapper -%}
{%- call field_wrapper(field) -%}
    <input id="{{ field.name }}" name="{{ field.name }}" type="text"
           value="{{ field.value or '' }}" class="ha-input" />
{%- endcall -%}
```
{% endraw %}

All widget templates (except `checkbox_input.html` which has a different label pattern) use this macro.

---

## CSS Architecture

### File Structure

CSS is organized as modular partials imported from a single entry file using `@import` with `@layer` for explicit cascade control. Browser requirement: Chrome 99+, Firefox 97+, Safari 15.4+.

```
src/hyperadmin/static/css/
  hyperadmin.css          → entry file (@layer declaration + @import only)
  _tokens.css             → :root design tokens (colors, spacing, typography, shadows)
  _dark-mode.css          → dark mode token overrides (three-way: class/data-attr/OS)
  _reset.css              → base reset (box-sizing, body defaults)
  _layout.css             → page, container, layout, content, toolbar
  _navbar.css             → navbar + dropdown
  _sidebar.css            → sidebar navigation
  _page-header.css        → page/section titles
  _card.css               → card component
  _table.css              → data table + sort + row actions
  _pagination.css         → pagination controls
  _search.css             → search input
  _forms.css              → form fields (input, select, textarea, checkbox, errors)
  _buttons.css            → buttons + variants + form actions bar
  _alerts.css             → alerts + toasts
  _login.css              → login page
  _filter.css             → filter bar
  _fieldsets.css           → fieldset groups + form grid layouts
  _theme-toggle.css       → theme toggle button + icon visibility
  _utilities.css          → links, icons, rotation transforms, HTMX indicator
  _accessibility.css      → skip-link, focus, touch targets, reduced motion, high contrast
  _responsive.css         → mobile/tablet media queries
```

### CSS Naming Convention

All classes use the `ha-` prefix to avoid conflicts with user-provided CSS:

- **Block**: `ha-{block}` — e.g., `ha-table`, `ha-btn`, `ha-sidebar`
- **Element**: `ha-{block}-{element}` — e.g., `ha-table-th`, `ha-sidebar-link`
- **Modifier**: `ha-{block}--{modifier}` — e.g., `ha-select--multi`, `ha-rotate--180`
- **Utility**: `ha-{utility}` — e.g., `ha-text-muted`, `ha-text-link`

### Design Tokens

Tokens are CSS custom properties on `:root`. Override them to theme HyperAdmin without touching markup:

```css
:root {
  /* Colours */
  --ha-color-primary:       #2563eb;
  --ha-color-primary-hover: #1d4ed8;
  --ha-color-primary-light: #dbeafe;
  --ha-color-danger:        #dc2626;
  --ha-color-success:       #16a34a;
  --ha-color-warning:       #ca8a04;
  --ha-color-text:          #374151;
  --ha-color-text-muted:    #6b7280;
  --ha-color-text-strong:   #111827;
  --ha-color-bg:            #f3f4f6;
  --ha-color-surface:       #ffffff;
  --ha-color-border:        #d1d5db;

  /* Typography */
  --ha-font-family: 'Inter', system-ui, -apple-system, sans-serif;
  --ha-font-size-sm:   0.875rem;
  --ha-font-size-base: 1rem;
  --ha-font-size-lg:   1.125rem;

  /* Shape */
  --ha-radius:    0.375rem;
  --ha-radius-lg: 0.5rem;

  /* Layout */
  --ha-sidebar-width: 16rem;

  /* Motion */
  --ha-transition: 150ms ease-in-out;
}
```

### Dark Mode

Dark mode uses a three-way system:

1. **Explicit class**: `.ha-theme-dark` on `<html>`
2. **Data attribute**: `[data-theme="dark"]` on `<html>`
3. **OS preference**: `@media (prefers-color-scheme: dark)` with `.ha-theme-light` guard

Dark values are defined once as `--_dark-*` private tokens, then mapped to semantic tokens in both the explicit and OS-preference selectors. This eliminates value duplication.

### Class Catalogue

#### Layout

| Class | Element | Purpose |
|---|---|---|
| `ha-page` | `<body>` | Background colour, font, min-height |
| `ha-container` | `<div>` | Max-width wrapper (1280 px), centred |
| `ha-layout` | `<div>` | Flex row: sidebar + content |
| `ha-content` | `<main>` | Flex-grow content area |
| `ha-list-toolbar` | `<div>` | Spacing wrapper for create button |
| `ha-detail-container` | `<div>` | Detail view wrapper |
| `ha-detail-fields` | `<div>` | Detail fields container |

#### Navigation

| Class | Element | Purpose |
|---|---|---|
| `ha-navbar` | `<nav>` | Fixed-height top bar with shadow |
| `ha-navbar-brand` | `<a>` | Logo / brand link |
| `ha-navbar-actions` | `<div>` | Flex container for theme toggle + user menu |
| `ha-navbar-user` | `<div>` | User menu container (Alpine.js) |
| `ha-dropdown` | `<div>` | Absolutely-positioned dropdown panel |
| `ha-dropdown-item` | `<a>` | Menu item with hover state |
| `ha-sidebar` | `<aside>` | Fixed-width sidebar |
| `ha-sidebar-nav` | `<ul>` | Navigation list |
| `ha-sidebar-link` | `<a>` | Nav link with active/hover state |

#### Forms

| Class | Element | Purpose |
|---|---|---|
| `ha-form-group` | `<div>` | Field wrapper (margin, stacking) |
| `ha-label` | `<label>` | Field label (bold, block) |
| `ha-required` | `<span>` | Red asterisk for required fields |
| `ha-input` | `<input>` | Text / number / date / email inputs |
| `ha-select` | `<select>` | Select dropdown |
| `ha-select--multi` | `<select>` | Multi-select height override |
| `ha-select--relation` | `<select>` | Semantic hook for relation selects |
| `ha-textarea` | `<textarea>` | Multi-line text |
| `ha-checkbox` | `<input[type=checkbox]>` | Checkbox (accent-color: primary) |
| `ha-checkbox-label` | `<label>` | Flex wrapper for checkbox + text |
| `ha-checkbox-text` | `<span>` | Label text beside checkbox |
| `ha-help-text` | `<p>` | Helper text below field (muted) |
| `ha-field-errors` | `<ul>` | Validation error list (italic, danger) |
| `ha-field-value` | `<div>` | Read-only field value in detail view |

#### Buttons

| Class | Modifier | Appearance |
|---|---|---|
| `ha-btn` | — | Base: padding, bold, border-radius, transition |
| `ha-btn` | `ha-btn-primary` | Primary background, white text |
| `ha-btn` | `ha-btn-danger` | Red background, white text |
| `ha-btn` | `ha-btn-secondary` | Outline button |
| `ha-btn` | `ha-btn-action` | Action button (detail view) |
| `ha-btn` | `ha-btn-ghost` | Transparent background |
| `ha-btn` | `ha-btn-link` | No background, coloured text |
| `ha-action-buttons` | `<div>` | Flex container for action buttons |

#### Tables

| Class | Element | Purpose |
|---|---|---|
| `ha-table-wrapper` | `<div>` | Card shell with shadow |
| `ha-table` | `<table>` | Full-width, border-collapse |
| `ha-table-header` | `<thead>` | Muted background |
| `ha-table-th` | `<th>` | Header cell padding, uppercase label |
| `ha-table-row` | `<tr>` | Row with hover highlight |
| `ha-table-cell` | `<td>` | Cell padding |
| `ha-table-sort-link` | `<a>` | Sort toggle link in header |
| `ha-action-link` | `<a>` | Inline action links (View, Edit) |
| `ha-action-delete` | `<button>` | Inline delete button |

#### Feedback

| Class | Purpose |
|---|---|
| `ha-alert` | Base alert (padding, border, radius) |
| `ha-alert-info` / `-success` / `-warning` / `-error` | Colour variants |
| `ha-toast-container` | Fixed top-right toast stack |
| `ha-toast` | Individual toast message |
| `htmx-indicator` | Hidden by default; shown during `.htmx-request` |

#### Utilities

| Class | Purpose |
|---|---|
| `ha-text-link` | Styled link with hover transition |
| `ha-text-muted` | Muted text colour |
| `ha-icon` / `ha-icon-sm` | SVG icon sizing |
| `ha-rotate--0` / `ha-rotate--180` | Rotation transforms with transition |

---

## HTMX Integration

HyperAdmin uses HTMX for every server round-trip that should not trigger a full page reload.

### How 422 Validation Errors Work

By default HTMX does not swap content for 4xx responses. `_base.html` includes a small event listener that opts 422 back in:

```javascript
document.addEventListener('htmx:beforeSwap', function (evt) {
  if (evt.detail.xhr && evt.detail.xhr.status === 422) {
    evt.detail.shouldSwap = true;
    evt.detail.isError = false;
  }
});
```

The server re-renders the form partial with inline errors and returns it with `status=422`. HTMX swaps it in place of the current form.

### Keyboard Shortcuts

`_base.html` also registers two search focus shortcuts: `Cmd/Ctrl+K` and `/`.

---

## Alpine.js Usage

Alpine.js is used sparingly, only for interactions that require no server round-trip:

| Location | Usage |
|---|---|
| `_navbar.html` | User dropdown toggle (`x-data`, `@click`, `@click.away`) |
| `_messages.html` | Toast auto-dismiss after 5 s (`x-data`, `setTimeout`) |
| `components/filter_bar.html` | Filter collapse/expand toggle |
| `components/fieldset.html` | Collapsible fieldset groups |

Server events (via `HX-Trigger` response headers) can bridge HTMX and Alpine. See `htmx_patterns.md` for the pattern.
