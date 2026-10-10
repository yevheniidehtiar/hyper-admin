An inline message about the page or form: success, info, warning and danger, optionally dismissible.

**Template:** `components/messages.html` (Starlette flash messages) and `components/alert.html` macro.

- `.ha-alert.ha-alert--<kind>`: icon, a bold title sentence, optional detail, optional dismiss button ("Dismiss", 24px target).
- Text is the status `-text` token on its `-soft` tint; the detail line uses `ha-color-text`. The border repeats the status colour.
- `role="alert"` for errors that block, `role="status"` for everything else.
- Flash messages appear under the page header after a redirect and stay until dismissed or the next navigation; for transient confirmation of an HTMX action use a Toast instead.
- Form errors: one danger alert at the top ("Please correct the 2 errors below.") that receives focus, plus field messages.

**Test ids:** `data-testid="alert-<kind>"`.
