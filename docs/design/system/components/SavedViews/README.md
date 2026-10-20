Per-user saved filter sets ("views") at the top of the FilterSidebar. In this version views are private: no sharing and no default view.

**Template:** `components/saved_views.html` (new), included at the top of the filter sidebar body. Spec: `docs/specs/filter-library.md` (endpoints `GET` / `POST /{model}/saved-views`, `DELETE /{model}/saved-views/{id}`; names are unique per user).

**The view provides:** the user's views for this model (id, name, query string), the id of the view matching the current URL, whether the current filters differ from it, and errors from the last save or rename.

- **List (`.ha-views__list`):**
  - Each view is a link to its query string (`?view={id}` resolves server-side), so it works without JavaScript and opens in a new tab.
  - The active view has `aria-current="true"`, a tick, semibold text and the primary tint, plus the screen-reader text "(active)". It is never marked by colour alone.
  - Long names truncate with an ellipsis, and the full name is in the link's accessible name.
- **Per-view actions:** a "…" button (label "Actions for view Late this month") opens Rename and Delete… in the flow under the row (`details.ha-view__more`), not as a floating menu, because the sidebar body scrolls and would clip a popup. Both are links (`?rename={id}`, `?delete={id}`) that HTMX enhances.
- **Save current view:**
  - "Save view" in the panel head opens an inline form (`.ha-view__edit`): Name, then Cancel and Save view.
  - Name taken: "You already have a view called “Late this month”. Pick another name, or update that view." The input keeps the text and focus.
  - On success, the new view is listed and becomes active.
- **Rename:** the row turns into the same inline form with the current name selected. Esc cancels.
- **Delete:** the Dialog as an alertdialog: "Delete the view “Late this month”?" and "Only the saved filters go. No orders change." Cancel is focused, and the danger button reads "Delete view".
- **Modified:**
  - When the URL's filters differ from the active view, a dashed box under the list says "Filters changed since you opened “Late this month”".
  - It offers "Update view" (POST, overwrites) and "Save as new…" (opens the save form with an empty name).
  - The view stays marked active until the user picks another.
- **Empty:** "Save the filters you use often. They show up here, only for you."

**Test ids:** `saved-views`, `saved-view-{id}`, `saved-view-save`, `saved-view-name-error`, `saved-view-modified`, `saved-view-delete-dialog`.

**Don't:**
- Save on every filter change.
- Show other users' views.
- Delete without the confirm.
- Use the accent colour for the active view.
