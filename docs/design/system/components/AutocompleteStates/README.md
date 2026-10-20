The states the autocomplete relation widget was missing: dependent fields, rich option rows, loading and no-match, the "+" popup create (including 403), and many-to-many tokens. It builds on the Combobox.

**Template:** `widgets/autocomplete.html`, `widgets/choices_options.html`, `widgets/popup_form.html`. Spec: `docs/specs/htmx-autocomplete.md`.

**The view provides:** field name and label, the choices URL, `depends_on` and its `placeholder`, `relation_display` (display template), the popup create URL (omitted when the target isn't registered or the user can't add), the selected value or values.

**Two layers, one markup.** The spec markup stays as is: a search input, the value `<select>`, and the "+" button.
- **Without JavaScript**, the native select is visible and carries the value. It is preloaded with the first 50 options, and its option text flattens the display template ("Acme Packaging — Lyon (SUP-214)").
- **With Alpine**, `.ha-autocomplete.is-enhanced` clips the select (it stays in the DOM, so the form and `select_option` in tests still work) and draws the Combobox listbox from the select's options.
- To make that possible, the choices fragment returns `<option value data-meta data-key>`. There is still one fragment and one source of truth.

- **Rich option row:** `.ha-option__label` (500 weight, the typed text in `<mark class="ha-match">`), `.ha-option__meta` (muted second line from `display_template`, for example "Acme — Paris"), and `.ha-option__key` at the end in mono. Selected rows use the primary tint. The keyboard-active row uses the hover surface. A row that is both gets a 2px ring.
- **Dependent field:**
  - While the parent is empty, the input is disabled with a dashed, sunken look (`.ha-combobox.is-waiting`). Its placeholder is the configured `placeholder` (default "Choose a supplier first"), and a help line says why.
  - If it's opened anyway, the listbox shows one info row.
  - When the parent changes, the field clears, says so in help text ("Cleared because the supplier changed.") and in its `role="status"`, and fetches again with `hx-include` of the parent.
- **Loading:** after the 200ms debounce, a spinner replaces the clear button and the list shows "Searching suppliers…". The status region says "Searching". Don't show "No results" while a request is in flight.
- **No match:** "No suppliers match “acm”." followed by a create option "Create “acm”…" (`.ha-option--create`). The create option appears only when the popup URL exists. It opens the popup with the typed text in the first field.
- **"+" button:** an icon button with `aria-label="Add supplier"` and `aria-haspopup="dialog"`, beside the input. It is disabled while a dependent field is waiting.
  - It loads `popup_form.html` into `#ha-popup-root` as the 640px Dialog. "Save and select" closes it on the `hyperadminPopupCreated` trigger and selects the new row.
  - **403:** the dialog stays open and swaps its body for a danger alert ("You can’t add suppliers." plus who can grant it) with one Close button. Focus moves to the alert's button.
- **Many-to-many:** the selected values are `.ha-chip` tokens inside `.ha-tokens` (label plus key). Each has its own remove button with the label "Remove Acme Logistics B.V.". Backspace in the empty input removes the last token. The listbox gets `aria-multiselectable="true"` and the hidden select is `multiple`.

**Test ids:** `autocomplete-{field}` (search input), `autocomplete-select-{field}` (value select), `autocomplete-add-{field}` ("+"), `popup-root` (dialog container), `popup-form`, `popup-form-field-{name}`, `popup-form-{name}-errors`, `popup-form-submit`. Options are reached by role and name.

**Don't:**
- Remove the select when enhancing. Clip it.
- Leave a dependent field holding a value that doesn't belong to the new parent.
- Hide the "+" when the user can't add only after a 403. Omit it server-side when the permission is known.
- Show the key as the main label.
