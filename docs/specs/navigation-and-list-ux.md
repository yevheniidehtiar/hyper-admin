# SDD: Navigation & List UX

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | — (stories in `.meta/epics/epic-v059-*`) |
| Milestone | v0.5.9 — Navigation & List UX |
| Created | 2026-11-01 |
| Last updated | 2026-11-01 |

---

## Problem

Functionality, performance and adoption are in place. The UI is what holds HyperAdmin back once an app has more than a handful of models.

- **Navigation does not scale.**
  - `routing.py:493-584` builds one flat `nav_items` list in registry insertion order.
  - `_sidebar.html` renders it as a single column.
  - With 20–60 models (typical for the dogfood apps) the sidebar is a long unsorted scroll.
  - There are no domain groups, no way to keep the few models a person uses daily at hand, and no way to jump to a model by typing.
  - Per-model `icon` exists, but it is an undocumented duck-typed attribute that no example sets.
- **List rows waste space.**
  - Every row carries three text buttons, View, Edit and Delete (`components/table_body.html:26-45`), so the actions column is often wider than the data.
  - The buttons are gated only by the static `AdminOptions.can_*` flags. A user without `change_<model>` still sees Edit and gets a 403 toast after clicking.
  - Delete uses the browser's native `hx-confirm` prompt, which is unstyled, untranslatable chrome, and which the design system already says to replace (`docs/design/system/README.md:168`).

The design system already specifies the target:
- AppShell grouped sidebar, collapsed rail and `nav-<model>` test ids (`docs/design/system/components/AppShell/README.md`)
- the DataTable title-cell link (`components/DataTable/README.md`)
- the destructive Dialog (`components/Dialog/README.md`)
- the Combobox pattern for the palette (`components/Combobox/README.md`)

None of it is implemented yet. This SDD turns those specs into an implementable plan and adds the pieces they leave open: pins, palette data and per-user row targets.

## Goals

- G1. Models can be grouped by domain, ordered, and given an icon from one documented place. Plugin sections take part in the same grouping.
- G2. The sidebar renders the AppShell grouped layout. Groups collapse, the sidebar collapses to an icon rail, and both states persist without a flash on load.
- G3. Each user can pin models and plugin pages. Pins are stored server-side, follow the user across devices, and show as a "Pinned" group at the top.
- G4. Cmd/Ctrl+K opens a palette that finds models, groups and plugin pages by name and lists recently visited pages and records. It never queries model tables.
- G5. List rows have no View or Edit buttons. The record's title cell is a real link and the whole row is clickable: edit for users who may change the record, detail for read-only users.
- G6. Delete is a red icon button that opens one shared confirm dialog, on the list, detail and edit pages.
- G7. Forms warn before unsaved changes are lost, keep Save in view, and save on Cmd/Ctrl+S.
- G8. Lists can be driven from the keyboard (`j`/`k`/Enter/`x`/`c`, `?` overlay), with an off switch for single-key shortcuts (WCAG 2.1.4).

## Non-Goals

- Palette search over **records** in model tables. This is a follow-up story (`st-v059-nav-05`): a per-model opt-in, a capped endpoint and permission filtering.
- Record history and audit timeline. This is a separate epic (`epic-record-history`) that needs its own SDD.
- Breadcrumbs and sidebar count badges. Both are specified in AppShell but are not part of this milestone.
- Column show/hide, a density toggle, and remembering list state when you come back from a record.
- Undo-after-delete or soft delete.
- Reordering pins by drag and drop. Pins are listed in the order they were pinned.
- A sidebar more than two levels deep (AppShell "Don't").

## BDD Scenarios

```
Scenario: models are grouped and ordered in the sidebar
  Given OrderAdmin(nav_group="Sales", nav_order=1) and CustomerAdmin(nav_group="Sales", nav_order=0)
  And   InvoiceAdmin(nav_group="Accounting")
  And   nav_groups=[NavGroup("Sales", order=0), NavGroup("Accounting", order=1)]
  When  an admin opens any admin page
  Then  the sidebar shows a "Sales" group with Customers then Orders
  And   an "Accounting" group with Invoices below it

Scenario: an ungrouped model stays visible
  Given TagAdmin with no nav_group and no app_label
  When  an admin opens any admin page
  Then  Tags is listed in the unnamed group at the top of the sidebar

Scenario: a plugin section merges into the group with the same label
  Given the permissions matrix plugin entry in section "Access"
  And   UserAdmin(nav_group="Access")
  When  an admin opens any admin page
  Then  one "Access" group lists Users and Permission matrix

Scenario: a collapsed group stays collapsed after reload
  Given the "Accounting" group is expanded
  When  the user collapses it and reloads the page
  Then  the "Accounting" group is collapsed in the server-rendered HTML

Scenario: the model of a detail page is the active nav item
  When  the user opens /admin/order/42/edit
  Then  the "Orders" nav item has aria-current="page"
  And   the "Order lines" item (/admin/orderline) does not

Scenario: pinning a model adds it to the Pinned group
  Given alice is signed in and has no pins
  When  alice pins "Orders"
  Then  a "Pinned" group appears at the top of the sidebar with Orders
  And   after signing in on another browser alice still sees Orders pinned

Scenario: pins are per user
  Given alice pinned Orders
  When  bob opens any admin page
  Then  bob's sidebar has no Pinned group

Scenario: a pin to a model the user can no longer view is hidden
  Given alice pinned Invoices and then loses view_invoice
  When  alice opens any admin page
  Then  Invoices appears neither in Pinned nor in Accounting

Scenario: the palette finds a model by group name
  Given the "Accounting" group contains Invoices and Bills
  When  the user presses Cmd+K and types "acco"
  Then  Invoices and Bills are listed as results
  And   pressing Enter on Invoices opens /admin/invoice

Scenario: the palette offers "New" only where allowed
  Given the user holds view_invoice but not add_invoice
  When  the user opens the palette and types "invoice"
  Then  the Invoices result has no "New invoice" action

Scenario: the palette lists recent records
  Given the user opened the edit page of order "ORD-1042"
  When  the user opens the palette with an empty query
  Then  "ORD-1042" is listed under Recent

Scenario: clicking a row opens the edit page for an editor
  Given alice holds change_order
  When  alice clicks anywhere on the row of order 42 outside its controls
  Then  /admin/order/42/edit opens

Scenario: clicking a row opens the detail page for a read-only user
  Given bob holds view_order but not change_order
  When  bob clicks the row of order 42
  Then  /admin/order/42 opens
  And   the row shows no delete button

Scenario: row controls do not trigger the row link
  Given Order has a bulk action and list_editable=["status"]
  When  the user ticks the row checkbox, or clicks the status cell
  Then  the row is selected, or the inline editor opens, and the page does not navigate

Scenario: delete asks for confirmation in a dialog
  Given alice holds delete_order
  When  alice clicks the delete icon on order "ORD-1042"
  Then  an alertdialog "Delete ORD-1042?" opens with focus on Cancel
  And   pressing Cancel closes it and the row remains
  And   confirming deletes the order and reloads the list

Scenario: leaving a dirty form asks first
  Given the user changed a field on the order edit form
  When  the user clicks a sidebar link
  Then  the browser asks to confirm leaving the page

Scenario: Cmd+S saves the form
  Given the user is on the order edit form
  When  the user presses Cmd+S
  Then  the form is submitted as if Save was clicked

Scenario: j/k move between rows and Enter opens one
  Given a list of 3 orders
  When  the user presses j twice and then Enter
  Then  the second row's link is opened

Scenario: single-key shortcuts can be turned off
  Given the user turns shortcuts off in the ? overlay
  When  the user presses j on a list
  Then  nothing happens
  And   Cmd+K still opens the palette
```

## Design

### Architecture

| Area | Module | Change | Story |
|---|---|---|---|
| Nav model | **new** `src/hyperadmin/core/navigation.py` | `NavGroup`, `NavItem`, `NavGroupNode`, `build_nav_tree()` (pure, no views import) | nav-01 |
| Wiring | `src/hyperadmin/routing.py` | calls `build_nav_tree()`; still publishes the flat `nav_items` global | nav-01 |
| Wiring | `src/hyperadmin/core/app.py` | `nav_groups=` keyword; passes the plugin nav into the tree; `nav_tree` Jinja global | nav-01 |
| Icons | `src/hyperadmin/static/icons/`, `templates/components/_icons.html` | ~22 domain icons, macro regenerated | nav-01 |
| Sidebar | `templates/_sidebar.html`, `static/css/_sidebar.css` | AppShell groups, collapse, rail | nav-02 |
| Pins | **new** `src/hyperadmin/navigation/` package: `pins.py` (`NavPin`, `NavPinService`) | table + service | nav-03 |
| Pins views | **new** `src/hyperadmin/views/nav_pins.py` | `POST`/`DELETE {prefix}/nav/pins` | nav-03 |
| Palette | **new** `templates/components/command_palette.html`, **new** `static/js/palette.js`, **new** `static/js/shortcuts.js`, `templates/_navbar.html`, `templates/_base.html` | dialog, data island, trigger, shortcut registry | nav-04 |
| Row target | `src/hyperadmin/views/dynamic/list_view.py` | `row_target`, `user_can_delete` in context | list-01 |
| Rows | `templates/components/table_body.html`, `components/table.html`, `static/css/_table.css` | title-cell link, stretched row, icon delete | list-02/03 |
| Dialog | **new** `templates/components/confirm_delete_dialog.html`, `templates/base.html`, `templates/detail.html`, `templates/form_layout.html` | shared confirm, detail/edit Delete, edit "View" link | list-02/03 |
| Forms | `templates/form_layout.html`, **new** `static/js/form_guard.js`, `src/hyperadmin/core/options.py` | dirty guard, sticky bar, Cmd+S, `warn_unsaved_changes` | kbd-01 |
| Keyboard | `static/js/shortcuts.js`, **new** `templates/components/shortcuts_overlay.html` | list shortcuts, `?` overlay | kbd-02 |

Dependency flow follows CONSTITUTION §1, with dependencies pointing inward:
- `core/navigation.py` imports nothing from `views/`. It receives the registry, the resolved plugin `NavEntry` list and the `nav_groups` argument as plain data.
- `navigation/pins.py` uses `core.adapters.open_session` the same way `filters/saved_views.py` does.
- `views/nav_pins.py` depends on the pins service.
- Templates read the `nav_tree` global plus the per-request pins and permissions.

No JS build is added. `palette.js`, `shortcuts.js` and `form_guard.js` are plain ES2019 files loaded from `base.html` and `_base.html` next to `primitives.js`. Together they stay under 8 KB minified-equivalent, to protect the 150 KB first-load budget.

### Data Model Changes

**`NavGroup`** (public, `hyperadmin.NavGroup`, frozen dataclass):

```python
@dataclass(frozen=True)
class NavGroup:
    label: str | LazyString       # matches nav_group / plugin section labels
    icon: str | None = None       # Lucide name; shown in the rail and the palette
    order: int = 0                # groups sort by (order, label)
    collapsed: bool = False       # default state before the user toggles it
```

**`NavItem` / `NavGroupNode`** (internal, `core/navigation.py`):

```python
@dataclass(frozen=True)
class NavItem:
    key: str              # pin target: model slug ("order") or "plugin:<url_name>"
    label: str | LazyString
    url: str              # relative to admin prefix, e.g. "/order"
    icon: str             # Lucide name; FALLBACK_ICON ("layout-grid") when unset
    permission: str | None  # "view_order" for models, NavEntry.permission for plugins
    create_url: str | None  # "/order/create" when can_create, else None
    create_permission: str | None  # "add_order"
    order: int
    testid: str           # "nav-order" / NavEntry.testid

@dataclass(frozen=True)
class NavGroupNode:
    slug: str             # "" for the unnamed group, else slugified label
    label: str | LazyString | None
    icon: str | None
    collapsed: bool
    items: tuple[NavItem, ...]
```

**ModelView / ModelAdmin class attributes.** These are documented on `core/model.py` and read with `getattr`, so third-party admin classes work unchanged.

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `icon` | `str` | `""` | Lucide name (now documented). Legacy icon-font classes still render as `<i class>`. |
| `nav_group` | `str \| LazyString \| None` | `None` | Group label; falls back to `app_label`, then the unnamed group |
| `nav_order` | `int` | `0` | Order inside the group; ties sort by label |

**`hyperadmin_nav_pin`** table (`navigation/pins.py`). It joins the `hyperadmin_*` metadata on import, like `hyperadmin_saved_view`, so `hyperadmin init-db` and `hyperadmin.auth.metadata()` (Alembic hosts) pick it up.

```python
class NavPin(SQLModel, table=True):
    __tablename__ = "hyperadmin_nav_pin"
    __table_args__ = (UniqueConstraint("user_key", "target", name="uq_hyperadmin_nav_pin"),)
    id: int | None = Field(default=None, primary_key=True)
    user_key: str = Field(index=True, max_length=255)   # request.state.user_key
    target: str = Field(max_length=255)                 # NavItem.key
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCNaiveDateTime)
```

`NavPinService(engine=None, session_factory=None)` has `list_for(user_key) -> list[str]`, `pin(user_key, target)` (idempotent) and `unpin(user_key, target)` (idempotent). It allows at most `MAX_PINS = 20` per user; a 21st pin raises `PinLimitError`, which the view turns into a toast.

### API / Protocol Changes

**`build_nav_tree`** (`core/navigation.py`):

```python
def build_nav_tree(
    models: Iterable[ModelNavSource],       # (model, admin_class, options) from the registry
    plugin_entries: Iterable[ResolvedNavEntry],
    groups: Sequence[NavGroup] = (),
) -> tuple[NavGroupNode, ...]
```

Rules:
1. A model's group label is `admin_class.nav_group`, then `app_label`, then `None` (the unnamed group). A plugin entry's group is its `section`, or "Plugins" when it has none.
2. Labels are matched by `str(label)` at build time, so lazy labels merge with plain labels that read the same in the default locale. The `LazyString` itself is kept for rendering.
3. Group order:
   - The unnamed group always comes first.
   - Groups declared in `groups` then sort by `(order, str(label))`.
   - Undeclared groups follow, sorted by label.
   - When nothing is configured, plugin groups keep their current place after the model groups.
4. Items sort by `(order, str(label))`. For plugins, `order` is `NavEntry.order`.
5. An empty group is dropped. Permission filtering happens at render time, because it is per request; a group whose items are all filtered out is not rendered.

The tree is built once in `generate_routes()` and published as the `nav_tree` Jinja global. `nav_items` (flat, same keys as today) stays published for host templates that override `_sidebar.html`.

**Pin endpoints** (`views/nav_pins.py`). They are registered only when auth is configured (a `user_key` exists).

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `{prefix}/nav/pins` | form `target=<NavItem.key>` | 200, `components/nav_pinned.html` fragment (`hx-swap-oob` for the item's toggle) |
| `DELETE` | `{prefix}/nav/pins/{target}` | — | 200, same fragment |

- Both are CSRF-protected by the existing `CsrfGuard`.
- An unknown `target`, or one the user may not view, returns 404. This avoids an oracle for model names.

**Template context.** No new view parameters. The sidebar reads `nav_tree`, `request.state.user_permissions` and `request.state.nav_pins`. The pins are loaded per request by a small dependency in the admin route class, and only when the pins feature is enabled.

**List view context** (`list_view.py`):

| Key | Value |
|---|---|
| `row_target` | `"update"` if `options.can_edit` and the user holds `change_<model>`; else `"detail"` if `options.can_detail` and the user holds `view_<model>`; else `None` |
| `user_can_delete` | `options.can_delete` and the user holds `delete_<model>` |

Both come from `_has_permission()`, at most two checks per page render. Object-level permissions are **not** evaluated per row. A row the object checker would deny still links to the page, which returns the existing 403 toast or page; this matches today's behaviour and keeps lists O(1) in permission calls.

**Palette data island.** `_base.html` renders `<script type="application/json" id="ha-nav-data">` with the permission-filtered tree:

```json
{"groups": [{"label": "Sales", "items": [
  {"key": "order", "label": "Orders", "url": "/admin/order", "icon": "receipt",
   "group": "Sales", "create_url": "/admin/order/create", "pinned": true}]}]}
```

- `create_url` is present only when `can_create` and the user holds `add_<model>`.
- Labels are rendered in the request locale.
- The island is escaped with `tojson`.

**Recent items.** `palette.js` keeps the last 8 visits in localStorage `ha-recent` (`[{label, url, kind}]`, newest first, deduplicated by url). Pages declare what to record with `<body data-ha-recent='{"label": ..., "url": ..., "kind": "record"|"list"}'>`:
- list pages record the model's plural name;
- edit and detail pages record the object's display string.

Reads and writes are wrapped in try/catch, so private windows simply have no recents.

**Shortcut registry** (`static/js/shortcuts.js`, `window.haShortcuts`):

```js
haShortcuts.register({ keys: "mod+k", description, handler, scope: "global" })
haShortcuts.register({ keys: "j", description, handler, scope: "list", single: true })
```

- `single: true` shortcuts are ignored while focus is in `input`, `textarea`, `select` or `[contenteditable]`, and while localStorage `ha-shortcuts` is `"off"`.
- Modifier shortcuts (`mod+k`, `mod+s`) are always on.
- `?` opens the overlay that lists the registered shortcuts and holds the on/off switch.
- The existing `_base.html` handler that focuses the search on Cmd+K moves into the registry: `mod+k` now opens the palette, and `/` still focuses the list search.

### UI details

**Sidebar (nav-02)** follows AppShell markup.
- Each group is `<div class="ha-nav-group" data-testid="nav-group-<slug>">`, containing an `<h2>` with a `<button aria-expanded aria-controls>` and then the `<ul>`.
- The unnamed group has no heading.
- Collapsed group slugs are kept in cookie `ha-nav-collapsed` (comma-separated, `SameSite=Lax`, path = admin prefix). The server reads the cookie, so the first paint is already correct.
- **Rail:** a toggle button (`panel-left-close` / `panel-left-open` icon, testid `sidebar-rail-toggle`) sets `data-collapsed` on the shell and cookie `ha-sidebar-rail=1`. In the rail, labels become screen-reader text, each item gets a `title` tooltip, and group headings collapse to a divider.
- **Active item:** `aria-current="page"` when the path equals the item url or starts with `url + "/"`. That is a segment match, so `/order` does not match `/orderline`.
- **Mobile:** the existing drawer behaviour (Alpine `sidebarOpen`, focus trap, Esc) is unchanged.
- The CSS moves from `docs/design/system/components/bundle.css` into `static/css/_sidebar.css`.

**Pins (nav-03).**
- The "Pinned" group (`data-testid="nav-pinned"`) renders first, and only when the user has visible pins.
- Each item gets a pin toggle button, testid `nav-pin-<key>`:
  - `aria-pressed`;
  - `aria-label` "Pin Orders" or "Unpin Orders";
  - icon `pin` or `pin-off`;
  - shown on row hover and on `:focus-within`, always shown on touch.
- The toggle posts with `hx-post` / `hx-delete` and swaps the Pinned group.
- A pinned item still appears in its own group.

**Palette (nav-04).**
- It is a native `<dialog class="ha-palette" data-testid="command-palette" aria-label="Search">` with:
  - an input `role="combobox"` (testid `palette-input`);
  - a `role="listbox"` of options (testid `palette-result`).
- Sections, in order: Pinned, Recent (empty query only), Models (by group), Pages (plugin entries).
- **Matching:** case- and accent-insensitive subsequence scoring over `label + " " + group`. A prefix match on the label ranks first. At most 20 results.
- **Keys:** ↑/↓ move, Enter opens, Shift+Enter (or the inline "New" button) opens `create_url`, Esc closes and returns focus.
- **Trigger:** the navbar shows a "Search… ⌘K" button (testid `palette-trigger`, the label says Ctrl+K on non-Mac platforms). It collapses to a search icon under `ha-bp-md`.
- **Without JS** the trigger is hidden (`x-cloak`) and the sidebar remains the navigation.

**Rows (list-02).**
- **Title cell:** the first column in `fields` that is not inline-editable becomes `<th scope="row">` with `<a class="ha-row-link" data-testid="row-link" href="{row url}">`.
- **Whole row clickable:** `.ha-table-row{position:relative}` plus `.ha-row-link::after{content:"";position:absolute;inset:0}`.
- **Controls stay usable:** checkbox cells, inline-edit cells, links rendered inside cells, and the delete button get `position:relative; z-index:1`, so they sit above the stretched link.
- **Hover:** `ha-surface-hover` and `cursor:pointer` on rows that have a link.
- **Mobile:** the card layout keeps the stretched link, so the whole card opens the record.
- When `row_target` is `None`, the title cell renders as plain text and the row is not interactive.
- The View and Edit buttons and their test ids (`row-view-link`, `row-edit-link`) are removed.
- **Detail page:** gains Edit (secondary, `pencil`, testid `detail-edit-link`) and Delete (testid `detail-delete-btn`) in its header, each gated like the row.
- **Edit page:** gains a "View" link (testid `form-view-link`) when `can_detail` and the user holds `view_<model>`, plus a Delete button in the form actions (testid `form-delete-btn`).

**Delete (list-03).**
- **Row delete button:** `<button class="ha-btn ha-btn--icon ha-btn--ghost ha-btn--danger-icon" data-testid="row-delete-btn" aria-label="Delete ORD-1042">`.
  - It shows the `trash-2` icon in `ha-color-danger-text`, with a tooltip (`components/tooltip.html`).
  - It renders only when `user_can_delete`.
- **Shared dialog:** one `components/confirm_delete_dialog.html` is included once in `base.html`: `<dialog class="ha-dialog" role="alertdialog" data-testid="dialog-confirm-delete">`.
  - The title is "Delete {object}?" and the description says "This cannot be undone."
  - Cancel comes first and gets the initial focus. The confirm button "Delete" uses `ha-color-danger`.
- **Wiring:** triggers dispatch `ha-confirm-delete` with `{url, label}`. On confirm, the dialog calls `htmx.ajax('DELETE', url, {source: dialog, swap: 'none'})`, so the CSRF header from `<body hx-headers>` applies. The server's existing `HX-Redirect` reloads the list, and errors (403/404/409) still arrive as the existing error toast.
- **Focus:** closing returns focus to the trigger.
- **Docs:** `docs/design/system/README.md` ("deletes still use `hx-confirm`") and the DataTable README (title link goes to edit or detail by permission) are updated in this story.

**Form safety (kbd-01).**
- **Guard:** `form_guard.js` marks `[data-testid=model-form]` dirty on the first `input` or `change` event and clears the flag on submit. While dirty:
  - `beforeunload` asks before leaving;
  - `htmx:confirm` asks before any htmx request whose target would replace the form.
- **Opt-out:** `AdminOptions.warn_unsaved_changes: bool = True`; set it to `False` per model.
- **Sticky save bar:** the form actions are `position:sticky; inset-block-end:0` on `ha-surface-raised`.
- **Cmd/Ctrl+S:** calls `form.requestSubmit()`, so validation and HTMX handlers run, and is a no-op outside forms.

**Keyboard (kbd-02).**
- **List shortcuts:**
  - `j`/`k` focus the next or previous `row-link`, skipping rows without one;
  - Enter follows the link (native);
  - `x` toggles the focused row's bulk checkbox;
  - `c` goes to `create-link`.
- **Overlay:** `?` opens `components/shortcuts_overlay.html` (testid `shortcuts-overlay`), with a switch labelled "Single-key shortcuts" (testid `shortcuts-toggle`).

### Configuration Changes

| Where | Name | Type / default | Story |
|---|---|---|---|
| `HyperAdmin(...)` keyword-only | `nav_groups` | `Sequence[NavGroup] = ()` | nav-01 |
| ModelView / ModelAdmin class | `nav_group`, `nav_order`, `icon` (documented) | see Data Model | nav-01 |
| `AdminOptions` | `warn_unsaved_changes` | `bool = True` | kbd-01 |

`nav_groups` goes on the constructor, not on `HyperAdminSettings`: the settings class is for scalar env-driven values ("All scalar configuration lives here"), and a list of objects does not belong in env vars. `disabled_plugins` is the precedent.

### New `data-testid`s

These are added to the CLAUDE.md reference table by the story that introduces them:
- `nav-<key>`, `nav-group-<slug>`, `nav-pinned`, `nav-pin-<key>`, `sidebar-rail-toggle`
- `command-palette`, `palette-input`, `palette-result`, `palette-trigger`
- `row-link`, `dialog-confirm-delete`, `detail-edit-link`, `detail-delete-btn`, `form-view-link`, `form-delete-btn`
- `shortcuts-overlay`, `shortcuts-toggle`

`row-view-link` and `row-edit-link` are removed.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Model has no `icon` | `FALLBACK_ICON` ("layout-grid") so labels align; the legacy icon-font class still renders as `<i>` |
| `nav_group` names a group not in `nav_groups` | Group is created with defaults, sorted after the declared groups by label |
| Two groups differ only in case ("sales" / "Sales") | Kept separate. `build_nav_tree` logs one warning per pair at startup |
| Auth disabled (no `user_key`) | Pins feature off: no toggles, no Pinned group, pin routes not registered. The palette still works without the Pinned section |
| Pin target model unregistered later, or plugin disabled | Row ignored at render; the stale row is deleted on the user's next pin or unpin |
| User loses `view_<model>` | Pinned entry hidden (permission filter at render); the pin row is kept, so it reappears if access returns |
| 21st pin | `PinLimitError` → 409 plus error toast "You can pin up to 20 pages" |
| Pin POST race (double click) | Unique constraint; the service treats IntegrityError as already pinned (idempotent) |
| Cookie `ha-nav-collapsed` holds unknown slugs | Ignored |
| Cookie or localStorage unavailable | Groups render from `NavGroup.collapsed`; no recents; shortcuts default on |
| First column is inline-editable | Title link goes on the first non-editable column. If every column is editable, an extra narrow cell holds a `chevron-right` link (`aria-label` "Open {object}") |
| Row contains its own links (FK display links) | `z-index:1` keeps them clickable above the stretched link |
| Text selection inside a row | Native link behaviour: dragging to select text does not navigate |
| `row_target` is `None` (no change and no view) | Plain title text; such users normally cannot reach the list (`view_<model>` gates it), but `can_detail=False` with `can_edit=False` is a valid config |
| Object permission denies a linked row | Existing 403 page or toast on open; deletes return the existing 403 toast |
| Delete returns 409 (FK IntegrityError) | Dialog closes; the existing error toast explains it |
| Dashboard (extends `_base.html`, no `base.html`) | Palette and shortcuts live in `_base.html` so they work there; the delete dialog lives in `base.html` (no deletes on the dashboard) |
| Host overrides `_sidebar.html` | Their template keeps receiving `nav_items`; the new globals are additive |
| RTL | Rail and active bar use logical properties; `chevron-right` uses `.ha-icon--mirror` |

## Migration & Backward Compatibility

- **No breaking API changes.** New attributes are optional. `icon` keeps its current semantics. `nav_items` keeps its shape.
- **One new table:**
  - `hyperadmin_nav_pin` is created by `hyperadmin init-db` and by demo-mode `create_tables`.
  - Alembic hosts get it from `hyperadmin.auth.metadata()`; `docs/guides/existing-app.md` §5 gains the hand-written operation next to `hyperadmin_saved_view`.
  - With the table missing, pins are logged once and disabled (no 500), the same guard saved views use.
- **Visible template changes:**
  - Hosts that override `components/table_body.html` keep their own row buttons.
  - E2E suites downstream that click `row-view-link` / `row-edit-link` must switch to `row-link`. This goes in the CHANGELOG under "Changed".
- **E2E and visual updates:**
  - Delete moves from native `confirm()` to an HTML dialog, so `page.on("dialog")` handlers (`tests/e2e/test_update_delete_view.py:47,60`) become role-based (`get_by_role("alertdialog")`).
  - Visual baselines (`tests/e2e/snapshots/responsive/`, `tests/e2e/snapshots/i18n/`) are refreshed on Linux in each UI story.

## Open Questions

- [ ] Milestone position: right after v0.5.8 (proposed), or after v0.5.5 finishes?
- [ ] Should the palette's empty state also offer "Create …" for the current model's list page? (Proposed: yes, as the first option on a list page.)
- [ ] `MAX_PINS = 20`: acceptable, or make it a setting?

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Pins in a DB table | Owner decision (2026-11-01). Pins follow the user across devices; the `SavedView` pattern already exists | localStorage (no schema change, per browser only) |
| Palette searches nav entries only in this milestone | Owner decision. Instant, no DB load, no per-model opt-in needed; record search follows as nav-05 | Records across models now (endpoint, perf caps, permission filtering) |
| Data island + client-side matching | Fewer than ~200 entries per admin; avoids a round trip per keystroke; the island is already permission-filtered | `hx-get` search endpoint per keystroke |
| Row link = stretched `<a>` in the title cell | Real link: middle-click, new tab, screen readers and no-JS all work; matches DataTable "title cell is the link" and "no other links per row" | `tr onclick` (not a link, inaccessible), `hx-get` on the row |
| Editors land on edit, read-only users on detail | Owner request: the click target follows what the user may do; the detail page stays reachable from the edit page's "View" link | Always detail (an extra click for the common case) |
| Model-level permission for row target, not object-level | Keeps the list at a constant number of permission calls; denial still enforced server-side on open | Per-row object checks (N extra queries per page) |
| Red delete = ghost icon button in `ha-color-danger-text`, solid `ha-color-danger` only on the confirm | Owner wants a red delete icon; the design system reserves the solid danger fill for the confirming action (`README.md` "Danger buttons") | Solid red icon button (two competing danger fills) |
| One shared dialog included once | One focus-managed element; triggers stay tiny | A dialog per row (DOM bloat on 100-row pages) |
| `nav_groups` on the `HyperAdmin` constructor | Settings are scalar and env-driven; `disabled_plugins` is the precedent | `HyperAdminSettings.nav_groups` |
| Group falls back to `app_label` | Apps that already pass `app_label` get domain groups for free | No fallback (everything ungrouped until configured) |
| Shortcut registry with an off switch for single keys | WCAG 2.1.4; one place for the palette, forms and lists | Per-feature key handlers (current `_base.html` handler) |
