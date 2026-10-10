A short, stacked notification that confirms an HTMX action, reports a failure, or flags an edit conflict.

**Template:** `components/toast.html`; the server sends it in an `HX-Trigger` event or an out-of-band swap into the toast region.

- Region: `<div class="ha-toasts" role="region" aria-label="Notifications" aria-live="polite">`, fixed to the block-end inline-end corner (mirrors in RTL), `ha-z-toast`, max three visible; newer on top.
- `.ha-toast` on `ha-surface-overlay` with `ha-shadow-lg`: status icon, bold title, one line of detail, optional action button, dismiss button.
- **Success:** auto-dismisses after 5s (thin timer bar), pauses on hover and focus. **Error:** `role="alert"`, stays until dismissed. **With action:** "Undo" for reversible deletes, keeps 10s. **Conflict** (v0.6.0 optimistic locking): warning icon, names who changed it, primary "Review changes" that opens the conflict dialog; never auto-dismisses.
- Toasts never carry the only copy of important information; the page state also reflects the change.

**Test ids:** `data-testid="toasts"` on the region; each toast `data-testid="toast-<kind>"`.
