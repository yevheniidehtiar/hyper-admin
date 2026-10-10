The frame around every admin page: navbar, grouped sidebar, breadcrumbs and page header, in expanded, collapsed and mobile-drawer forms.

**Template:** `layouts/_base.html` with `components/navbar.html`, `components/sidebar.html`, `components/breadcrumbs.html`, `components/page_header.html`.

**The view provides:** the nav tree (groups → items with `label`, `url`, Lucide `icon` name, optional `count` and its meaning), the current URL, breadcrumb trail, page title, page actions (max one primary).

- Root: `<div class="ha-root ha-shell" data-collapsed="false">`. Collapsing sets `data-collapsed="true"` (Alpine, persisted in a cookie) and narrows the column to `ha-sidebar-width-collapsed`; labels stay in the DOM as screen-reader text.
- Sidebar groups are `<div class="ha-nav-group">` with an `<h2>` and a `<ul>`. Each item is `<a class="ha-nav-item">` with an icon and `.ha-nav-item__label`. Active item: `aria-current="page"`; the 3px `ha-color-brand` bar sits on its inline-start edge and mirrors in RTL.
- Count badges: `.ha-count` with an `aria-label` that says what is counted ("3 overdue"); `.ha-count--attn` (accent) only for something that needs action.
- Below `ha-bp-md` the sidebar leaves the grid and opens as `.ha-drawer` from the menu button (its label switches to "Close menu", `aria-expanded` and `aria-controls` point at the drawer, focus moves into it, Esc closes, scrim `ha-color-scrim`). Drawer links carry `data-testid="drawer-nav-<model>"` so they do not collide with the sidebar's.
- Navbar end: connection status (`.ha-live`), locale switcher, theme toggle (`aria-label` names the theme it switches to), user menu.
- Breadcrumbs: `<nav aria-label="Breadcrumb"><ol>`, separator chevrons are `aria-hidden` and `.ha-icon--mirror`; the last crumb is `aria-current="page"` text, not a link.
- Page header: `ha-h1` title on the start side, actions on the end side, wrapping under the title when the label is long.

**Accessible names / test ids:** `<header>` banner `data-testid="navbar"`; `<nav aria-label="Main" data-testid="sidebar">`; items `data-testid="nav-<model>"`; page action `data-testid="add-<model>"`.

**Don't:** put more than two levels in the sidebar; hide the active state behind hover; show a count badge without saying what it counts.
