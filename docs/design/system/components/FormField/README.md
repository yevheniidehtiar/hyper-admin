A labelled input with help text and validation, covering the 13 form widgets plus the autocomplete relation.

**Template:** `widgets/<widget>.html`, wrapped by `components/field.html`.

**The view provides:** label, name, value, widget, required, read-only, disabled, help text, errors, choices.

- Wrapper `.ha-field`: `<label class="ha-label" for>`, the control, then `.ha-help` and/or `.ha-errmsg`, linked with `aria-describedby`.
- **Required:** a red asterisk (`aria-hidden`) plus the native `required`. When most fields are required, mark the optional ones with `.ha-opt` "(optional)" instead.
- **Focus:** border and 2px ring in `ha-color-focus-ring`. **Error:** `aria-invalid="true"`, 2px `ha-color-danger-text` border, message with an icon under the field; the form also shows a danger alert at the top counting errors and focus moves there.
- **Read-only:** dashed `ha-color-border`, transparent fill, still selectable and copyable. **Disabled:** `ha-surface-sunken`, `ha-color-text-disabled`, with help text saying why.
- Widgets: text, textarea, number and float (`.ha-input--num`, `inputmode="decimal"`), checkbox (`.ha-check`, 18px box, 24px target), select, multiselect (`.ha-tokens` chips), datetime (native, shown in `settings.timezone` with the zone named in help text), file, relation select (a select plus an icon button "Add another account" with `aria-haspopup="dialog"` that opens the popup create dialog), relation multiselect (`.ha-tokens`), integer number (`type="number"`, `inputmode="numeric"`), autocomplete relation (`role="combobox"` + `.ha-listbox`, shows the key in mono, last option "Create …").
- Currency and unit affixes: `.ha-affix` — the symbol position follows the locale.
- Comfortable vs compact only changes `ha-control-height`; labels stay above inputs at every width.

**Test ids:** `data-testid="field-<name>"` on the control. The accessible name is always the visible label.
