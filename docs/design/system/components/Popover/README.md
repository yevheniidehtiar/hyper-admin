Small floating layers attached to an element: a tooltip for a short label or reason, a popover for richer, interactive detail (help, presence, AI provenance).

**Template:** `components/tooltip.html` macro `tip(content, placement="above")` and `components/popover.html` macro `popover(trigger, title, body, actions)`.

**Needed by:** truncated cells, icon buttons, disabled reasons, chart points, v0.6.1 presence, v0.8 AI provenance, field help everywhere.

**Tooltip** (`.ha-tip` wrapper + `.ha-tooltip`):
- Shows on hover **and** keyboard focus (CSS `:hover, :focus-within`, so it works without JavaScript), and on tap; Esc hides it without moving focus (Alpine adds `.is-dismissed`). It stays while the pointer is over it (WCAG 2.2, 1.4.13).
- Text only, at most about 80 characters, 12px on `ha-color-text-strong` with `ha-surface-raised` text (inverts in dark), arrow pointing at the trigger. `--below` when there is no room above.
- Never the only label: an icon button keeps its `aria-label`; the tooltip repeats it visually (`aria-hidden="true"`). When the tooltip adds information (a disabled reason, a full truncated value) it has `role="tooltip"` and the trigger points at it with `aria-describedby`.
- **Disabled with a reason:** use `aria-disabled="true"` instead of `disabled`, so the button can still take focus and show why.

**Popover** (`<details class="ha-layer">` + `.ha-popup.ha-popover`):
- For anything with structure or actions: a title, a few lines, a definition list, up to two buttons. `role="dialog"` with `aria-labelledby` the title; focus moves into it, Esc or the close button returns focus to the trigger, and it is not modal.
- Variants in the preview: field help (circle-help trigger, a link to the guide), presence details (who, editing which field, since when), AI provenance (`.ha-ai-label` "AI-generated" trigger in `ha-color-accent`; what it is based on, when, Accept / Discard).
- Width 300px, `ha-shadow-md`, `ha-z-popover`; placement flips to stay inside the viewport.

**Test ids:** popovers that tests open get `data-testid="popover-<name>"` on the trigger; tooltips are asserted through the trigger's accessible description.

**Don't:** put links or buttons in a tooltip; open popovers on hover alone; use a popover where the content is needed to finish the task (put it on the page).
