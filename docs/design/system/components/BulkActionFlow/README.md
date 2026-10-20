Run one action over many rows: select rows in the list, fill a parameter form if the action has one, then read a per-row result and retry the failures.

**Template:** the bar and checkbox column in `components/table.html`; `components/bulk_form.html` (parameter step); `components/bulk_result.html` (result). Spec: `docs/specs/bulk-actions.md`.

**The view provides:** the bulk actions (`name`, `label`, `form`), the selected ids (stringified with `pk.to_str`), the form fields and errors, `confirm_url`, the outcomes (`BulkRowResult(id, status, detail)`), `failed_ids`, `bulk_endpoint_url` and the audit-log URL filtered to this run.

- **Checkbox column:** rendered only when the model has at least one `bulk=True` action. Each row box is `<input type="checkbox" name="ids" form="<bar id>">`, so the boxes post with the bar without wrapping the table in a form. Accessible name: "Select ORD-1042". The header box is "Select all orders on this page".
- **Bar (`.ha-bulkbar` + `__count`, `__pick`, `__end`):** "3 selected", a `<select name="action">` whose first option is "Choose an action…", Run (primary), and "Clear selection" (ghost, at the end). Actions that open a form end in "…" ("Reassign…"). Without JavaScript the bar is always shown and the count reads "Select rows, then choose an action".
- **One URL per action:** the routes are `/{model}/actions/{name}/bulk`, but a `<select>` can't change a form's action without JavaScript. Two options: add a small `POST /{model}/actions/bulk` that redirects with 307 using `action`, or render one submit button per action with `formaction` inside `<noscript>`. The first is recommended. Alpine sets `form.action` on change.
- **No selection:** Run with nothing checked shows "Select at least one row, then press Run." with a warning icon, in the bar (`.ha-bulkbar--warn`, `role="alert"`) or as the server flash. The server still answers 400 "Selection required" to a crafted POST.
- **Parameter step: dialog with HTMX, page without it.** It is the same `bulk_form.html`. With HTMX it opens in the 640px Dialog (`#ha-popup-root`). Without JavaScript the bar's POST renders it as a page with breadcrumbs.
  - Title repeats verb and count ("Reassign 3 orders"), then one plain sentence about what happens.
  - The selected keys show as mono tags and are carried as `<input type="hidden" name="ids">`.
  - Fields are ordinary FormFields. The primary button repeats the title. Cancel closes the dialog, or links back to the list on the page.
  - A validation error re-renders the step with the field errors, a danger alert ("1 field needs fixing. Your 3 selected orders are kept.") and the same hidden ids.
- **Result (`.ha-bulk-result--ok | --mixed | --failed`):**
  - The summary line has an icon and words: "2 of 3 orders reassigned. 1 failed.", "All 3 orders reassigned to …", "No orders reassigned. All 3 failed."
  - A tally of status pills, and a proportion bar (`.ha-progress__segments`; forbidden is hatched).
  - A compact table: record link plus a muted second line, a status pill, and the detail in plain words that says how to fix it. On narrow containers the table becomes cards.
  - Status pills: Done (round marker), Failed (diamond), Forbidden (square). The word always carries the meaning, and the marker shape is a second cue.
  - Row order: problems first, then done. Above about 20 rows, the done rows fold into `<details>` ("Show the 199 reassigned orders"), which also works without JavaScript.
  - Actions:
    - "Retry failures (n)", a POST form with the non-ok ids. Omitted when nothing failed. `failed_ids` includes forbidden rows; consider leaving those out, since they would fail again.
    - "Back to orders" (primary).
    - A link to the audit entries for this run. There is no rollback button: the audit log is the rollback surface.
- With HTMX, a successful confirm returns the result fragment with `HX-Retarget` to the main region and closes the dialog.

**Test ids:** `bulk-checkbox` (row boxes), `bulk-bar`, `bulk-action-select`, `bulk-run-btn`, `bulk-warning`, `bulk-form`, `bulk-form-field-{name}`, `bulk-form-{name}-errors`, `bulk-confirm-btn`, `bulk-result`, `bulk-result-row`, `bulk-result-status-{id}`, `bulk-retry-form`, `bulk-retry-link`.

**Classes the in-flight templates should switch to:**

| Current class | Design system class |
|---|---|
| `ha-form-field` | `ha-field` |
| `ha-field-errors` | `ha-errmsg` |
| `ha-btn-primary` | `ha-btn--primary` |
| `ha-btn-secondary` | plain `ha-btn` |

Add `ha-pill` to `ha-bulk-status`, and wrap the result table in `.ha-table-wrap` with `.ha-table`.

**Don't:**
- Run the action on Run when it has a form.
- Disable Run when nothing is selected. Pressing it explains instead.
- Show raw exception text in the detail column.
- Stop at the first failure.
- Put a destructive action in the accent colour.
