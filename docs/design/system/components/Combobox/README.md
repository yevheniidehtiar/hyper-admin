A text input that searches a server-side list and picks one or many records: relation fields, filters, the tenant picker, the role picker and, later, the command palette.

**Template:** `widgets/combobox.html` (single) and `widgets/combobox_multiple.html`; options come from the existing choices endpoint as an HTML fragment (`hx-get` on input, `hx-trigger="input changed delay:250ms"`).

**Needed by:** v0.5.5 AutocompleteWidget, v0.7.0a FK preload threshold (a relation select becomes a combobox above the threshold), v0.5.6 multi-FK filters, v0.5.7 role picker, v0.5.3 tenant picker, v0.8 command palette.

**ARIA:** `<input role="combobox" aria-expanded aria-controls aria-autocomplete="list" aria-activedescendant>` + `<ul role="listbox">` of `<li role="option" aria-selected>`; `aria-multiselectable="true"` for the multiple variant. A visually hidden `role="status"` reports "3 results", "Searching", "No results" so screen readers hear what changed.

- **Control:** leading search icon, the input, then a tools slot with spinner (loading), clear (`aria-label="Clear contact"`) and a chevron that opens the full list. Multiple: selected values are `.ha-chip`s inside `.ha-tokens`; Backspace in an empty input removes the last chip.
- **Option anatomy:** label with the typed text in `<mark class="ha-match">` (bold + underline, never colour alone), one meta line (city, type), the key in mono at the end. Selected: `ha-color-primary-soft`; keyboard-active: `ha-surface-hover`, or a 2px focus-ring outline when both.
- **States, all in the preview:** closed; minimum characters not reached (default 2, with the total count); loading (after a 250ms debounce, spinner in the field and a "Searching…" row); results; grouped results ("Recent" first); paged results (20 per page, "Showing 20 of 312 · Load more"); no results with "Create contact “…”" when the user may add; server error with Retry.
- **Keyboard:** Down/Up move, Enter selects, Esc closes (a second Esc clears), Tab selects the active option and moves on, Home/End inside the input stay text-editing keys.
- **Without JavaScript:** below the FK threshold the server renders a plain `<select>`; above it, an input for the key (mono) plus a "Browse…" link that opens the related list in popup mode (Django's `raw_id_fields`).
- Long lists never load all at once: the server returns at most 20 rows per request.

**Test ids:** `data-testid="combobox-<field>"` on the wrapper; options are reached by role and name.

**Don't:** search on every keystroke without the debounce; show "No results" while a request is still running; select the first option on blur.
