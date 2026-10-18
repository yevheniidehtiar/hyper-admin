---
type: story
id: st-conflict-05
title: "refactor(core): discover component stylesheets instead of a hand-maintained @import list"
status: todo
priority: medium
assignee: null
labels:
  - size:M
  - planned
  - area:core
  - layer:ui
  - frontend
estimate: null
epic_ref:
  id: ep-conflict-avoidance-01
created_at: 2026-10-18T00:00:00Z
updated_at: 2026-10-18T00:00:00Z
---

## Summary

Every UI feature appends an `@import` line to `static/css/hyperadmin.css`, so parallel UI PRs conflict on the same
hunk. Plain CSS cannot glob, so move the per-feature list out of the file: component partials live in
`static/css/components/` and are discovered at startup (sorted by file name, layer read from a `/* @layer <name> */`
header comment, default `components`). `_base.html` emits one `<link>` per discovered partial after the core
stylesheet. `hyperadmin.css` keeps only the `@layer` order and the core partials (fonts, tokens, reset, layout). A new
feature then adds a file and touches no shared list.

This is a seam story: merge it before the next wave of UI stories.

## Files to Change

- `src/hyperadmin/views/stylesheets.py` (new) — discovery (cached), returns ordered `(href, layer)` entries
- `src/hyperadmin/static/css/hyperadmin.css` — drop the component `@import` lines
- `src/hyperadmin/static/css/components/*.css` — move existing component partials here (`git mv`)
- `src/hyperadmin/templates/_base.html` — loop over the discovered stylesheets
- `tests/unit/test_stylesheets.py` (new)
- `tests/e2e/snapshots/` — refresh only if rendering changes (it should not)

`views/` and `_base.html` are owned by v0.5.8 while it is in flight; schedule this story after that wave or with the
owner's agreement.

## Scenarios

```
Scenario: New partial is picked up without editing a shared file
  Given a new file static/css/components/_widget.css
  When  the admin renders any page
  Then  the page links _widget.css after hyperadmin.css

Scenario: Layer comes from the header comment
  Given a partial starting with "/* @layer utilities */"
  When  stylesheets are discovered
  Then  it is assigned to the utilities layer

Scenario: Rendering is unchanged
  Given the existing component partials moved into components/
  When  the visual E2E suite runs
  Then  no snapshot differs
```

## Acceptance Criteria

- [ ] New partial is picked up without editing a shared file
- [ ] Layer comes from the header comment
- [ ] Rendering is unchanged
- [ ] 100 % coverage of changed lines; `poe lint` passes

## Parent

- Epic: `epic-conflict-avoidance`
