A modal for confirming destructive actions, resolving edit conflicts, and creating a related record in a popup.

**Template:** `components/dialog.html` — a native `<dialog class="ha-dialog">` opened with `showModal()` (Alpine), so focus trapping, Esc to close and the backdrop (`ha-color-scrim`) come from the browser.

- Layout: head (status glyph, `ha-h3` title, one-paragraph description), optional body, foot on `ha-surface-base` with actions on the end side: cancel first, confirming action last.
- **Confirm destructive:** `role="alertdialog"`, title is a question with the count ("Delete 3 invoices?"), description names what goes with it and that it cannot be undone; the confirm button repeats the verb and count on `ha-color-danger`. Initial focus on Cancel.
- **Conflict "someone else changed this":** names the person and when, shows a `<table class="ha-diff">` of the conflicting fields (field as row header, yours vs theirs as columns), and offers Keep editing / Overwrite with mine / Load their version (primary).
- **Popup create:** the related model's create form in the body, Save adds the new record to the originating relation field and closes. Without JS it is a normal link to the create page with `_popup=1`.
- Closing returns focus to the element that opened it. Max width 480px (create forms 640px); full-screen sheet under `ha-bp-md`.

**Test ids:** `data-testid="dialog-confirm-delete"`, `"dialog-conflict"`, `"dialog-create-<model>"`.
