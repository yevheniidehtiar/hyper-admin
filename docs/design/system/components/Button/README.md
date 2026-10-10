Triggers an action: primary, secondary, ghost, danger and accent, plus icon-only, in every interaction state.

**Template:** `components/button.html` macro `button(label, variant="secondary", icon=None, type="button", loading=False)`.

- `.ha-btn` alone is **secondary** (raised, `ha-color-border-strong` edge). `--primary` (`ha-color-primary` / `ha-color-on-primary`): one per view, the thing the page is for. `--ghost`: Cancel and low-weight actions. `--danger`: only the confirming button of a destructive flow. `--accent` (violet): rare, at most one per screen, for new or AI features.
- `--icon` is square at the control height, min 24px, and **must** have an `aria-label` naming action and object. `--sm` for toolbars and table bulk bars.
- States: hover (`ha-color-primary-hover` / `ha-surface-hover`), pressed (inset shade), focus (2px ring, 2px offset), **loading** (spinner replaces the icon, label says what is happening — "Saving…" — and `aria-busy="true"`, `aria-disabled="true"`; HTMX sets this via `hx-indicator`), disabled (`ha-surface-sunken`, `ha-color-text-disabled`).
- Links that navigate are `<a class="ha-btn">`; actions are `<button>`; submit buttons are `type="submit"` so forms work without JS.
- Labels wrap rather than truncate; icons sit on the inline-start side and only mirror if directional.

**Test ids:** `data-testid="btn-<action>"` (e.g. `btn-save`, `btn-delete`).
