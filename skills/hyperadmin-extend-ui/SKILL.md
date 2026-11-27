---
name: hyperadmin-extend-ui
description: Extend or override the HyperAdmin UI beyond the declarative options - Jinja template and block overrides, per-model templates, widget template overrides, CSS design tokens, the terminal and classic theme presets, dark mode, extra stylesheets, HTMX fragments, data-testid conventions, Playwright end-to-end tests and screenshot baselines. Use when the user says "override the list template", "change the admin colours", "rebrand the admin", "theme preset", "custom CSS", "change how a field renders", "HTMX partial", "add an E2E test for the admin", or "visual regression".
---

# Extend the HyperAdmin UI

The UI is server-rendered Jinja2 with HTMX 1.9 and Alpine.js 3, styled by plain CSS (`ha-*`
classes, `--ha-*` custom properties). No build step. Try the declarative options first (the
`hyperadmin-define-ui` skill); override templates only for what they cannot express, because
every copied template has to be re-checked on each HyperAdmin upgrade.

Docs: Frontend Overview, Widgets, HTMX Patterns (`docs/frontend/`), Override templates in
Getting Started, API Reference > Application (settings table).

## Flow

1. State what should change and check that no `AdminOptions`/`ModelAdmin` option does it.
2. Pick the smallest seam from the table below.
3. Extend built-in templates by name and call `{{ super() }}` instead of copying where a block
   exists; copy a file only when there is no block to hook.
4. Verify: render the page with TestClient (status 200, your marker present), then in a
   browser in both light and dark mode and both presets if you support both.
5. Add an E2E test that uses `get_by_role` / `get_by_label` / `get_by_test_id`.

| Need | Seam |
|---|---|
| Colours, fonts, radius, spacing | CSS tokens in an extra stylesheet |
| Overall look | `HyperAdminSettings(theme_preset="terminal" \| "classic")`, `theme="auto" \| "light" \| "dark"` |
| One model's list/detail/form page | `{app_label}/{model}/{view}.html` in your template dir, extending the built-in page |
| Every page of one kind | `{view}.html` in your template dir (shadows the built-in one) |
| How one input type renders everywhere | Copy of `widgets/<name>.html` in your template dir |
| Navbar / sidebar | Copy of `_navbar.html` / `_sidebar.html` (hotspot: re-sync on upgrades) |
| A page of your own | A plugin page (`hyperadmin-new-plugin` skill) |

## Template directories and resolution

```python
from hyperadmin.core.settings import HyperAdminSettings

settings = HyperAdminSettings(template_dirs=["admin_templates"])  # searched before built-ins
admin = Admin(app, engine=engine, settings=settings)
```

For model pages the view looks up, first match wins:

1. `{app_label}/{model_name}/{view_name}.html`
2. `{app_label}/{model_name}/default.html`
3. `{app_label}/{view_name}.html`
4. `{app_label}/default.html`
5. `{view_name}.html`
6. `default.html`

`view_name` is `list`, `detail`, `create` or `update`; `model_name` is the lowercased class
name. Steps 1-4 apply **only when the model was registered with an `app_label`**:
`site.register(Invoice, InvoiceAdmin, app_label="billing")`. Without it, a `list.html` in your
directory replaces the list page of every model.

Plugin template directories come after yours and after the built-ins: a plugin cannot override
built-in templates, and you can override a plugin's by placing the same relative path in your
directory.

## Built-in templates and blocks

| Template | Extends | Blocks |
|---|---|---|
| `_base.html` | - | `title`, `messages`, `navbar`, `sidebar`, `content`, `command_palette`, `shortcuts_overlay` |
| `base.html` | `_base.html` | adds the popup root, autocomplete and delete-dialog scripts in `messages`. Extend this one for your own pages |
| `list.html` | `list_layout.html` | `title`, `content`, `list_container` |
| `detail.html` | `detail_layout.html` | `title`, `content`, `detail_title`, `detail_actions`, `detail_fields` |
| `create.html`, `update.html` | `form_layout.html` | `title`, `content`, `form_title`, `form_header_actions`, `form_attributes`, `form_body`, `form_actions` |

Partials: `_navbar.html`, `_sidebar.html`, `_messages.html`, `components/*.html` (table,
pagination, filter sidebar, fieldset, inline formset, command palette, confirm dialog, ...),
`components/_macros.html` (`field_wrapper(field)`), `components/_icons.html`
(`icon(name, class)`). Read them in the installed package:
`python -c "import hyperadmin, pathlib; print(pathlib.Path(hyperadmin.__file__).parent / 'templates')"`.

Per-model override that adds a banner above the built-in list:

```jinja
{#- admin_templates/billing/invoice/list.html -#}
{%- extends "list.html" -%}
{%- block content -%}
  <div class="ha-alert ha-alert-info" data-testid="invoice-banner">Invoices lock on the 5th.</div>
  {{ super() }}
{%- endblock -%}
```

Jinja globals available in templates include `site_title`, `site_header`, `admin_prefix`,
`theme`, `theme_preset`, `nav_items`, `plugin_nav`, `visible_nav_tree()`, `nav_pinned_items()`,
`csrf_token()`, and `_()` for translations. For a custom sidebar use `visible_nav_tree()` (what
the current user may view) and `nav_pinned_items()` (`None` when pins are off).

## Widgets

A field's widget is picked from its type (see `hyperadmin-define-ui`). There is no
per-field widget option on `AdminOptions`. To change how a widget renders everywhere, copy
`widgets/<name>.html` into your template directory and edit it. Files: `autocomplete`,
`checkbox_input`, `choices_options`, `date_input`, `datetime_input`, `file_input`,
`float_input`, `image_input`, `multiselect_input`, `number_input`, `popup_form`,
`relation_multiselect_input`, `relation_select_input`, `select_input`, `text_input`, `textarea`.
Each receives `field` (`name`, `label`, `required`, `help_text`, `value`, `errors`) and `widget`
(`htmx_attrs`). Keep `id="{{ field.name }}"` so `<label for>` and `get_by_label` keep working.

## CSS tokens and theme presets

- `theme_preset="terminal"` (default) writes `data-ha-preset="terminal"` on `<html>`:
  near-black ground, acid-green accent, square corners, JetBrains Mono for structure.
- `theme_preset="classic"` uses the base values in `_tokens.css` / `_dark-mode.css`
  (teal, rounded).
- `theme="auto"` follows the OS; users can toggle; the choice is kept in `localStorage`
  (`ha-theme`).

Token names are the same in both presets: `--ha-color-primary`, `--ha-color-primary-hover`,
`--ha-color-on-primary`, `--ha-color-accent`, `--ha-color-danger`, `--ha-color-success`,
`--ha-color-warning`, `--ha-color-text`, `--ha-color-text-muted`, `--ha-color-text-strong`,
`--ha-color-bg`, `--ha-color-surface`, `--ha-color-border`, `--ha-surface-base`,
`--ha-surface-raised`, `--ha-font-family`, `--ha-font-mono`, `--ha-font-size-*`,
`--ha-radius`, `--ha-radius-*`, `--ha-space-*`, `--ha-shadow-*`, `--ha-sidebar-width`,
`--ha-chart-1` ... `--ha-chart-6`. The full list is `static/css/_tokens.css` in the package.

Overrides must match the preset's selectors, or the preset wins on specificity:

```css
/* admin.css */
:root[data-ha-preset="classic"] { --ha-color-primary: #7c3aed; --ha-color-primary-hover: #6d28d9; }
:root[data-ha-preset="classic"][data-theme="dark"] { --ha-color-primary: #a78bfa; }
:root[data-ha-preset="terminal"] { --ha-color-primary: #7c3aed; }
:root[data-ha-preset="terminal"][data-theme="dark"] { --ha-color-primary: #a78bfa; }
```

Dark mode is set three ways: class `.ha-theme-dark` / attribute `data-theme="dark"` on `<html>`,
or `prefers-color-scheme: dark` while no explicit light choice is stored. Cover the media query
too if you override dark values for "auto" users.

### Adding a stylesheet

`_base.html` has no `<head>` block and there is no setting for extra stylesheets. Two ways
that work:

1. **Every page except login:** copy the package's `_messages.html` into your template
   directory and append a `<link>`. The browser applies a `<link rel="stylesheet">` in the body.
2. **Some pages:** in a per-model override, put the `<link>` inside `{% block content %}`
   before `{{ super() }}`.

Serve the file from the host app, outside the admin prefix:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/assets", StaticFiles(directory="assets"), name="assets")
# admin_templates/_messages.html ends with:
#   <link rel="stylesheet" href="/assets/admin.css">
```

A plugin serves its own static files with `admin.plugins.set_static_dir(...)` at
`{prefix}/static/plugins/<name>/` and links them with
`{{ url_for('static', path='/plugins/<name>/file.css') }}` inside its templates.

## HTMX fragments

- List pages answer an `HX-Request: true` request with the table fragment
  (`<div id="model-list">...`); search, sort, filters and pagination swap it.
- `body` carries `hx-headers` with the CSRF token whenever auth is configured, so `hx-post`,
  `hx-put` and `hx-delete` from your templates pass the CSRF check. A plain `<form method=post>`
  needs `{{ csrf_input() }}` (renders the hidden `csrf_token` input; empty without auth).
- `_base.html` swaps 422 responses (re-rendered forms with errors) and shows the toast for
  403/404/409 responses that set `HX-Retarget`. Return 422 with the re-rendered fragment for
  validation errors in your own HTMX endpoints.
- HTMX does not swap other error statuses: a fragment endpoint that must show an error state
  in place should return 200 with that state.
- Load a fragment lazily: `<div hx-get="{{ admin_prefix }}/reports/orders-revenue/chart?embed=1" hx-trigger="load"></div>`.

Fragment endpoint in a plugin router:

```python
@router.get("/stats", name="myplugin-stats", response_class=HTMLResponse)
async def stats(request: Request) -> HTMLResponse:
    template = "myplugin/_stats.html" if request.headers.get("HX-Request") else "myplugin/stats.html"
    return admin.templates.TemplateResponse(request, template, {"count": 3})
```

## data-testid conventions

Add a `data-testid` to new interactive or assertable elements, named `<view>-<element>`.
`ha-*` classes are for styling; tests must not select on them. Built-in ids:

| Element | `data-testid` |
|---|---|
| Sidebar / nav link / nav group / pin toggle | `sidebar` / `nav-{key}` / `nav-group-{slug}` / `nav-pin-{key}` |
| List table / row / row link / row delete | `list-table` / `list-row` / `row-link` / `row-delete-btn` |
| Search / filters toggle / page size | `search-input` / `filters-toggle` / `page-size`, `page-size-{n}` |
| Pagination | `pagination-info`, `pagination-prev`, `pagination-next`, `pagination-page` |
| Sort link | `sort-{field_name}` |
| Create link / form / sticky actions bar | `create-link` / `model-form` / `form-actions` |
| Field errors / error summary | `{field_name}-errors` / `error-summary` |
| Detail fields / edit link / delete | `detail-fields` / `detail-edit-link` / `detail-delete-btn` |
| Edit page view link / delete | `form-view-link` / `form-delete-btn` |
| Delete confirm dialog | `dialog-confirm-delete` |
| Command palette / input / result / trigger | `command-palette` / `palette-input` / `palette-result` / `palette-trigger` |
| Shortcuts overlay | `shortcuts-overlay` |
| Request-failure toast | `request-error-toast` |
| Reports dashboard grid / card / stat | `dashboard-grid` / `widget-{key}` / `stat-{key}` |

## End-to-end tests (Playwright)

Install `pytest-playwright` and `uvicorn`, run `playwright install chromium`. One scenario per
test, with `# Given / # When / # Then` comments:

<!-- check: complete -->
```python
# tests/e2e/test_admin_products.py
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Page, expect


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    from main import app  # your FastAPI app with the admin mounted

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_created_product_appears_in_the_list(page: Page, live_server: str) -> None:
    # Given the create form of products is open
    page.goto(f"{live_server}/admin/product")
    page.get_by_test_id("create-link").click()

    # When the user fills it in and saves
    page.get_by_label("Name").fill("Lamp")
    page.get_by_label("Price").fill("12.5")
    page.get_by_test_id("form-actions").get_by_role("button", name="Create").click()

    # Then the product list shows the new row
    page.goto(f"{live_server}/admin/product")
    expect(page.get_by_test_id("list-table")).to_contain_text("Lamp")
```

Use a throwaway database for the server (a temp-file SQLite URL, or a test schema), and sign in
through the login page or seed a session when auth is on.

## Screenshot baselines

- Screenshots differ by OS, CPU architecture, font rendering and browser build. Generate and
  compare baselines in the same environment (for example the CI Linux image or a Docker
  container), never a laptop against CI.
- Fix the viewport, the theme (`theme="light"` or set `localStorage['ha-theme']`) and the preset
  in the test; the default `theme="auto"` follows the machine.
- Mask or freeze moving content: dates, counts, toasts, realtime status, autofocus carets.
- Refresh baselines in the same change that alters the UI, and review the image diff.
- Every HyperAdmin upgrade can move pixels; expect to re-approve baselines after upgrading.
