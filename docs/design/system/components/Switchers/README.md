Navbar menus to switch tenant (v0.5.3) and language and timezone.

**Template:** `components/tenant_switcher.html`, `components/locale_switcher.html`.

- Trigger: `.ha-switch-btn` showing the current value ("Noordzee Energie", "English · CEST") with a chevron; `aria-haspopup` and `aria-expanded`.
- Menu: `.ha-menu` on `ha-surface-overlay` with `ha-shadow-md`. Tenant picker is a `role="listbox"` with a search field on top once there are more than seven tenants; each option shows a two-letter `.ha-tenant-dot` and the name; the current one is `aria-selected="true"`, bold, with a check.
- Language menu: `role="menuitemradio"` items, each language in its **own** name and script, with its `lang` and `dir` set ("العربية" right-aligned). Timezone section shows the IANA name and offset in mono.
- Switching is a POST form per option (works without JS); the response reloads with the new `<html lang dir>`.

**Test ids:** `data-testid="tenant-switcher"`, `"locale-switcher"`.
