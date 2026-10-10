First-run, no-results, 403, 404 and 500 pages and skeleton loading.

**Template:** `components/empty_state.html` macro, `errors/403.html`, `errors/404.html`, `errors/500.html`.

- `.ha-empty`: a 48px glyph tile (icon) or the status code in mono `ha-color-brand`, an `ha-h4` heading that says what is going on, one muted sentence that says what to do, and at most two actions.
- **First run:** names the model in the plural and offers Add (primary) and Import (secondary) when available.
- **No results:** quotes the search, offers Clear filters.
- **403:** names what is not accessible and the permission codename; **404:** says the record may have been deleted and shows its ID; **500:** owns the error, shows a request reference in mono and a Reload button. Error pages keep the app shell so people can navigate away.
- **Skeletons:** `.ha-skel` blocks shaped like the content they replace, `aria-busy="true"` on the container; pulse turns off under reduced motion.

**Test ids:** `data-testid="empty-first-run"`, `"empty-no-results"`, `"error-403|404|500"`.
