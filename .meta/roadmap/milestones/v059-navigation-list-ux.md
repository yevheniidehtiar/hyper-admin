---
type: milestone
id: v059-nav-01
title: "v0.5.9 — Navigation & List UX"
status: todo
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

**Roadmap position: right after v0.5.8 (proposed 2026-11-01; the owner may move it).**
Functionality, performance and adoption are in place; the UI is what holds the admin back
once an app has more than a handful of models.

- **Find things** — sidebar groups by domain with icons, collapsible groups and an icon rail,
  per-user pinned models, and a Cmd/Ctrl+K palette over models, groups, pages and recent items.
- **Leaner lists** — no View/Edit buttons: the row opens edit (or detail for read-only users);
  delete is a red icon with a proper confirm dialog.
- **Don't lose work** — unsaved-changes guard, sticky save bar, Cmd/Ctrl+S.
- **Keyboard** — j/k/Enter/x/c on lists and a `?` overlay with an off switch.

Spec: [`docs/specs/navigation-and-list-ux.md`](../../../docs/specs/navigation-and-list-ux.md).

Epics: `epic-v059-navigation`, `epic-v059-compact-list-rows`, `epic-v059-form-safety-keyboard`.
