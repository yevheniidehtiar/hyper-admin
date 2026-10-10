The Lucide (ISC licence) outline icons the components use (25, `receipt` for Bills included), at 20px with a 1.5px stroke, with `stroke="currentColor"` so an inlined icon takes the text colour in both themes. (The design-system artifact keeps a #4B5565 copy so the files preview as images.)

Mirror in RTL with `.ha-icon--mirror`: `chevron-right` (and the other chevrons when used for back/forward). Never mirror: `check`, `circle-check`, `arrow-up`/`arrow-down` (sort and delta), `search`, `globe`, `calendar`, `bar-chart-3`.

**In this repository:** the 25 icons are vendored in `src/hyperadmin/static/icons/`. Inline them through a Jinja2 `icon(name)` macro; add further icons from the same pinned Lucide release.
