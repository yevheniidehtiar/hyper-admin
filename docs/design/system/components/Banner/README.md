A full-width notice under the navbar for state that is about the session or the app, not the page's own content: tenant context, stale record, connection, rate limit, maintenance.

**Template:** `components/banners.html` renders the region; views and middleware add banners to `request.state.banners` (`kind`, `message`, `detail`, `actions`, `dismissible`, `id`).

**Needed by:** v0.6.0a stale record, v0.5.3 tenant context, v0.6.0b connection lost, v0.7.0b rate limit (429 with Retry-After), v0.5.2 SSO errors, maintenance mode.

**Banner or Alert?** An Alert sits inside the content and is about that page or form ("Could not save the invoice"). A Banner sits above the content, stays across navigation and is about the session or the system. Use a Toast for something that just happened.

- Region: `<div class="ha-banners" role="region" aria-label="Notices">`, sticky under the navbar. Most severe first: danger, warning, context, info, success. Show at most two; the rest collapse into "+N more notices".
- Anatomy: icon, `.ha-banner__text` (a bold sentence plus a `<span>` detail in body colour), `.ha-banner__actions` at the end (Compare, Reload, Switch tenant, Retry), and a dismiss button only when dismissing is safe.
- **Kinds:** `--danger` (rate limit, sign-in failure), `--warning` (record changed since opened, connection lost), `--context` (tenant you are working in; never dismissible), `--info` (read-only or maintenance window), `--success` (back online; removes itself after 5s).
- **Rate limit:** the countdown (`.ha-countdown`) comes from `Retry-After`; Retry stays disabled until it reaches 0.
- **Stale record (v0.6.0a):** "This invoice changed since you opened it." with Compare (opens the conflict dialog) and Reload; it appears when the realtime channel or a version check says so, before the user saves.
- ARIA: `role="alert"` for danger and warning when they appear during use; `role="status"` otherwise. Do not re-announce banners on every page load.

**Test ids:** `data-testid="banners"`, and one per kind: `banner-tenant`, `banner-stale`, `banner-rate-limit`, `banner-maintenance`, `connection-lost`.

**Don't:** use a banner for marketing or tips; stack more than two; let a banner cover the page header (it pushes content down).
