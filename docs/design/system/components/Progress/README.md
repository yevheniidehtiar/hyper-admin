Shows how far a long task has got: bulk actions, exports, imports and uploads, in a page, a toast, an upload row or a button.

**Template:** `components/progress.html` macro `progress(label, value=None, max=100, value_text="", state="", size="md")`; the server re-renders it over HTMX polling (`hx-trigger="every 1s"`) or a realtime event until the job ends.

**Needed by:** v0.5.5 bulk jobs, v0.3.2 uploads, v0.5.4 exports, v0.7.1 imports.

- Anatomy: `.ha-progress__head` (label + value text), the track with `role="progressbar"`, `aria-valuemin/max/now` and an `aria-valuetext` that says it in words ("48%, 12 of 25 pages"), and an optional `.ha-progress__foot` for time left, status and actions.
- The bar width comes from `style="--value: 48%"`, rendered by the server; it fills from the inline start, so from the right in RTL.
- **Indeterminate** (`.ha-progress--indeterminate`, no `aria-valuenow`): when the size is unknown ("Counting rows"); switch to determinate as soon as a total is known. Under reduced motion the bar stands still.
- **States:** running (`ha-color-primary`), done (`--success`, with the next action: "Download CSV"), partly failed (`--warning`, "18 of 20 done · See the 2 failures"), failed (`--danger`, the reason and Retry). Each state has a word and an icon, not only a colour.
- **Steps** (`.ha-progress__segments`): multi-stage jobs, "Step 3 of 5 · Validating rows".
- **Small** (`--sm`, 4px): upload rows and toasts. **In a button:** spinner plus "Exporting… 40%", `aria-busy="true"`.
- Cancel is always available while running; cancelling ends in the failed state with "Cancelled".
- Announce progress politely and rarely: `aria-live="polite"` on the value text, updated every 10%, and the final state once.

**Test ids:** `data-testid="progress-<job>"` (`progress-export`), `toast-progress`.

**Don't:** show a determinate bar that jumps backwards; leave a finished bar on screen without saying what happened; block the page while a job runs (run it in the background and show a toast).
