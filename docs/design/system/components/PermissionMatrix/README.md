One page to edit what a group may do: models down the side, actions across, a checkbox per cell. It edits one group at a time, with no roles and no inheritance.

**Template:** `templates/permissions/matrix.html` (new) at `/admin/permissions-matrix/?group_id=`, posting a diff to `/admin/permissions-matrix/save`. Spec: `docs/specs/permission-matrix-ui.md`.

**The view provides:**
- The groups (id, name, member count) and the selected group with its `version`.
- The registered models grouped by app (label, `app.model`, the applicable actions including extras such as Export).
- The granted codenames and the object-rule count per model.
- After a save: the rejected cells with reasons, or the conflict or not-found outcome.

- **Header (`.ha-perm-head`):** a Group select (a GET form; at about 15 or more groups use the Combobox with search) and a note: "Changes apply to everyone in Editors." Switching group with unsaved changes asks first.
- **Grid (`.ha-table.ha-perm` in `.ha-table-wrap.ha-perm-wrap`):**
  - Rows are models with an `app.model` caption, grouped under quiet `th scope="rowgroup"` bands.
  - Columns are View · Add · Change · Delete, then extras, then "Object rules". An action that doesn't apply prints `—` with the screen-reader text "Export does not apply to customers".
  - Every cell is a real checkbox (`name="perm" value="{app}.{model}.{action}"`) whose label is a sentence: "Editors can change orders".
  - The first column and both header rows are sticky. The wrapper scrolls; the page doesn't.
- **Column select-all:** a tri-state checkbox in each header ("Editors can view every model"). It shows indeterminate when some rows are on. It is drawn by Alpine only, because it submits nothing.
- **Unsaved changes:**
  - A changed cell gets a dashed ring around its box (`td.is-changed`) and the screen-reader text "(unsaved)". It is marked by shape, not colour.
  - The sticky save bar (`.ha-savebar`) reads "3 unsaved changes", then Discard (`type="reset"`) and Save changes (primary).
  - `beforeunload` warns while the count is above 0. Without JavaScript the bar is always there and the form posts the full grid.
- **Object rules cell:** a pill button, either "2 rules" (shield icon) or a dashed "Add". It opens the ObjectPermissionPopover (`aria-haspopup="dialog"`, `aria-expanded`). Object rules save on their own and never count as unsaved changes.
- **Outcomes:**
  - **Saved:** the Toast "Permissions saved" ("3 changes for Editors"), and the dashed rings clear.
  - **409:** a warning Banner: "Permissions changed elsewhere. Reload to see the latest. Nothing was saved; your 3 changes are still on the page." It has a Reload link.
  - **Rejected cells (403 per cell):** a danger Alert, "2 changes weren’t saved. You can only grant permissions you have yourself:", listing the cells. Each rejected cell gets a solid danger ring, a ✕ icon, and `aria-describedby` with the reason. The other changes are saved.
  - **Group deleted:** an empty state, "The group Editors no longer exists. Someone deleted it while you were editing. Nothing was saved.", with "Choose another group".
  - **No registered models:** an empty state.
  - **403 for the page:** the error card.
- **Phone (container under 640px, `.ha-perm--cards`):** one card per model, with its name, caption, and boxed checkboxes that show their short visible label ("Change", `.ha-perm__short`), then the Object rules pill. The full sentence stays the accessible name.

**Test ids:**
- `permission-matrix`
- `perm-group-select`
- `perm-form`
- `perm-{model}-{action}`
- `perm-object-{model}`
- `perm-savebar`
- `perm-save`
- `perm-discard`
- `perm-conflict`
- `perm-rejected`
- `perm-group-gone`
- `perm-empty`
- `perm-forbidden`
- `toast-success`

**Don't:**
- Save each checkbox immediately. The matrix is a diff with one Save; only object rules save immediately.
- Mark changes by colour alone.
- Grey out permissions the editor lacks. Show them, and explain on save.
- Let the grid widen the page.
