Per-record rules for one group and model ("Editors may change INV-0142"), opened from the Object rules cell of the PermissionMatrix. Each change saves immediately.

**Template:** `templates/permissions/object_rules.html` (new), a fragment from `GET /admin/permissions-matrix/object/{group}/{model}`, posted to the same URL. Spec: `docs/specs/permission-matrix-ui.md`.

**The view provides:** the group and model labels, the rules (record pk, display, secondary line, action), the record autocomplete URL, the available actions, and the result of the last add or remove.

- **Anchoring:**
  - A non-modal `role="dialog"` popover (`.ha-popover.ha-objrules`, 380px), anchored under the cell's pill button (`aria-expanded="true"`, `aria-controls`).
  - Esc or the close button returns focus to the pill.
  - Under 640px it becomes a bottom sheet: fixed, full width, top corners rounded, at most 85vh, and scrolling inside.
- **Title:** "Object rules · Editors · Orders". The group and model names are muted.
- **Entries (`.ha-objrules__list`):** the record as a link (truncates) with a muted second line, the action as a neutral pill, and a remove icon button labelled "Remove rule for INV-0142". Each remove button is a POST form.
- **Add rule:** "Add rule" in the footer opens an inline row (`.ha-objrules__add`). It has a record autocomplete (the AutocompleteStates widget, `autocomplete-object_id`), an action select, and an Add button. Add is the only commit, and the row closes once the rule is saved.
- **Saving and confirmation:**
  - Every add or remove saves at once, and repeating it is idempotent. There is no Save button.
  - Confirmation is inline, in the popover's polite status (`.ha-inline-status`): "Rule for ORD-1047 added.", or "Rule for ORD-1039 removed." with Undo.
  - A failed remove keeps the row and says "Couldn’t remove the rule for ORD-1042. Try again." (`--error`).
  - On success the server sends `HX-Trigger: permissions-saved` so the cell's count updates.
- **States:**
  - Loading: two skeleton lines.
  - Empty: "No object rules. Group permissions apply."
  - Error: "Couldn’t load the rules." with a Retry link.
  - The footer always explains: "Saved as you go. Group permissions still apply."

**Test ids:**
- `object-permission-popover`
- `objrule-add`
- `objrule-remove-{pk}`
- `objrule-empty`
- `autocomplete-object_id`

**Don't:**
- Trap focus. It's a popover, not a modal, except as the phone sheet.
- Count object rules in the matrix's unsaved changes.
- Remove without a way back: offer Undo.
