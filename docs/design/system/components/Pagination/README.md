Moves through a long list: numbered pages, prev/next only, and a page-size select.

**Template:** `components/pagination.html`.

- `<nav class="ha-pager" aria-label="Pagination">`: result range on the start side ("Showing 126–150 of 290", numbers in `.ha-num`), page list in the middle, "Per page" select on the end side.
- Pages are links (`?page=6`), the current one `aria-current="page"` on `ha-color-primary`. Show first, last, current ± 1 and ellipses.
- First page: Previous is `aria-disabled="true"` text, not a link. Last page: same for Next. Chevrons are `.ha-icon--mirror`.
- Prev/next-only variant for keyset pagination or unknown totals: two secondary buttons with `rel="prev|next"`.
- Changing page size resets to page 1 and keeps filters.

**Test ids:** `data-testid="pagination"`, `"page-size"`.
