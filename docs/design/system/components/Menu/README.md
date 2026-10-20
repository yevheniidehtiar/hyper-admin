A dropdown list of actions or toggles opened from a button: row actions, bulk actions, export, column visibility, the user menu.

**Template:** `components/menu.html` macro `menu(trigger_label, items, align="start")`; an item is `{label, icon, href | post_url, description, shortcut, danger, disabled_reason, pressed}`.

**Needed by:** v0.5.5 bulk actions, row actions, v0.5.4 export, v0.5.6 saved views, v0.8 plugin actions.

**Pattern: a disclosure, not an ARIA `menu`.** `<details class="ha-layer">` with `<summary class="ha-btn">` as the trigger and `<div class="ha-popup ha-menu">` holding real links (`<a class="ha-menu__item">`) and POST forms (`<form method="post"><button class="ha-menu__item">`). Without JavaScript it opens, closes and submits; screen readers read ordinary links and buttons. Alpine adds: arrow keys and Home/End move focus, type-ahead, Esc closes and returns focus to the trigger, a click outside closes, only one menu is open at a time, and the popup flips up (`.ha-popup--up`) or to the end (`.ha-popup--end`) when it would leave the viewport.

- Trigger: a text button with a chevron ("Actions"), or an icon button whose `aria-label` names the object ("More actions for INV-2026-0142").
- Item anatomy: optional 20px icon, label, optional one-line `.ha-menu__desc`, optional end slot (`.ha-kbd` shortcut, or a mirrored chevron for a submenu). Height 36px, 44px under `(pointer: coarse)`.
- Group with `.ha-menu__label` headings and `<hr>` dividers; at most about 9 items before grouping or splitting.
- **Disabled with a reason:** `aria-disabled="true"` (stays focusable), the reason as the description, linked with `aria-describedby`. Never hide an action a user expects without saying why.
- **Danger:** `.ha-menu__item--danger` last, after a divider, label ends with "…" and opens the confirm dialog; never runs directly.
- **Toggle items** (columns, filters): `<button aria-pressed="true|false">` with the `.ha-menu__check` icon.
- **Submenu:** opens to the inline end (mirrors in RTL) on hover, focus or Right arrow; on touch it replaces the menu with a "Back" item. Keep to one level.
- Popup: `ha-surface-overlay`, `ha-shadow-md`, `ha-radius-lg`, `ha-z-popover`; max height 420px, then it scrolls.

**Test ids:** the trigger carries the menu's id (`row-actions`, `bulk-actions`); items keep their view ids (`row-edit-link`, `row-delete-btn`).

**Don't:** put the only copy of an action in a menu when there is room for a button; nest menus two levels deep; use a menu for navigation between pages (that is the sidebar).
