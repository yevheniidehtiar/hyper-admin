Groups fields into fieldsets and edits related rows inline, stacked or tabular, with add, delete-marked and row-error states.

**Template:** `components/fieldset.html`, `components/formset_tabular.html`, `components/formset_stacked.html`.

- Fieldset: `<fieldset class="ha-fieldset"><legend>`; collapsible ones are `<details class="ha-fieldset">` with a chevron that rotates (and mirrors in RTL). Collapse only secondary groups; never a group that holds an error (open it on render).
- Tabular inline: a `.ha-table.ha-formset` inside a card; every input has an `aria-label` with the row number ("Line 2 description"). Running totals sit in `<tfoot>`, `.ha-num`.
- **Add row:** a ghost "Add another line" button; HTMX inserts a blank row and focuses its first input. Without JS, the server renders `extra` blank rows.
- **Delete marked:** the row's delete checkbox is checked → `.is-deleted`: `ha-color-danger-soft` fill, struck-through read-only values and a "Will be deleted on save" pill. Unchecking restores it. Nothing is deleted until Save.
- **Row error:** `.has-error` adds a 3px `ha-color-danger-text` edge on the inline-start side; field errors sit under their input.
- Stacked inline: each row is a fieldset card with a "Line 2" legend and a delete checkbox in its header.

**Test ids:** `data-testid="formset-<prefix>"`, `"formset-add"`, rows `data-testid="formset-<prefix>-<index>"`.
