How each field type renders inside a table cell, including null, overflow and truncation.

**Template:** `components/cells/<type>.html`, picked by the adapter from the SQLModel/SQLAlchemy column type; override per model with `list_display_types`.

- **text**: `ha-color-text`; the record title `ha-color-text-strong` 600. Long text: `.ha-trunc` (28ch) with the full value in `title` for the mouse, `tabindex="0"` so keyboard focus unfolds it, and the full value in the card layout.
- **number / money / percent**: `.ha-num` (tabular, end-aligned). Money formatted by the locale with the currency from the row, narrow no-break space before the symbol where the locale wants one; negatives with a true minus and `ha-color-danger-text`.
- **date / datetime**: `<time datetime="…">` with the locale format; datetimes add the zone abbreviation of `settings.timezone` in muted text. Never relative ("3 days ago") in a list without the absolute date in `title`.
- **boolean**: icon + word ("Yes" check / "No" cross), never a coloured dot alone.
- **status pill**: `.ha-pill` + `--success | --warning | --info | --danger`, neutral by default. The word carries the meaning; the dot repeats it.
- **relation**: a link to the related record's detail page, text `ha-color-primary-text`.
- **id / key**: `.ha-mono`, shortened with an ellipsis in the middle-free tail ("7f3c9a2e-41b0…") with the full key in `title` and a copy button on the detail page.
- **image**: `.ha-thumb` 32px, `ha-radius-sm`, with `alt` from the record title.
- **null**: an em dash in `ha-color-text-muted` plus visually hidden "empty". Never "None" or "null".

**Test ids:** cells inherit the row's; add `data-testid="cell-<field>"` only where a test needs a single cell.
