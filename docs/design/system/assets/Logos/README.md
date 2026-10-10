The HyperAdmin mark is an "H" built from table rows, knocked out of a rounded tile. Use the files as they are; never redraw, recolour the rows or add effects.

- `hyperadmin-mark.svg` — full colour: tile #0D9488 (`ha-color-brand`, light), rows #FFFFFF. Sidebar, login card, docs. Minimum 16px.
- `hyperadmin-mark-mono.svg` — one ink, #0B1220, rows cut out so the ground shows through. Print, embossing, single-colour contexts; recolour its one fill to #FFFFFF on dark grounds.
- `hyperadmin-favicon.svg` — the cut-out mark in #0D9488 (3.7:1 on a white tab, 4.3:1 on #202124 and 3.2:1 on #35363A dark tabs, 2.9:1 on a grey #DEE1E6 inactive tab). The asset store strips `<style>`; the copy shipped as `static/hyperadmin/favicon.svg` may add a `prefers-color-scheme: dark` rule that switches it to #2DD4BF.
- `hyperadmin-wordmark.svg` — mark + "HyperAdmin" (Inter SemiBold "Hyper", Regular "Admin", outlined) in ink #121926, for light grounds. Minimum 96px wide.
- `hyperadmin-wordmark-dark.svg` — the same in #F2F5F9 with the #2DD4BF tile and #0B1220 rows, for `ha-surface-base` dark.

Clear space on every side: one sixth of the mark's height. Inside a host app, the navbar shows the host's `site_title` next to the mark, not the wordmark.

**In this repository:** the shipped files are in `src/hyperadmin/static/img/`. The repository copy of `hyperadmin-favicon.svg` keeps its `prefers-color-scheme: dark` switch to #2DD4BF (the design-system artifact store strips `<style>` from SVGs, so its copy has none).
