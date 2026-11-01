# SDD: Realtime in the full-demo and ERP example apps

| Field | Value |
|---|---|
| Author | Claude Code / Yevhenii Dehtiar |
| Status | Approved |
| Issue | #784, #785 (Epic #331) |
| Milestone | v0.6.0b — Live CRUD Notifications |
| Created | 2026-11-01 |
| Last updated | 2026-11-01 |

---

## Problem

None of the apps in `examples/` turns realtime on. Two realtime features exist today, but they
can only be seen in the E2E test app `tests/e2e/_realtime_app.py`:

- presence on edit pages, from v0.6.1;
- server-side CRUD events, from PR #776 (#310 and #311).

The browser side of live notifications follows in #312. Without a demo app wired for realtime,
nobody can try these features by hand: not the maintainers, not a reviewer of #312, and not a
visitor to the hosted demo.

The two showcase apps are the natural place for this:

- **`examples/full-demo`**: the umbrella app booted by the qualification suite. It seeds three
  users (`alice`, `bob`, `viewer`), so a two-browser demo works out of the box.
- **`examples/erp`**: the hosted public demo on Render (`render.yaml`, `deploy/demo/Dockerfile`)
  and the target of the multi-worker load test (`docker-compose.loadtest.yml`).

Between them, the two apps can show both configuration styles from the notifications SDD:
opting in a few models, and opting out a noisy one. They can also show the single-process
in-memory backend and the multi-worker Redis backend.

## Goals

- `full-demo` runs with realtime on and with **per-model opt-in**: notifications are off globally
  and on only for `Order` and `Product`. A two-browser walkthrough (alice and bob) is documented
  in its README.
- `erp` runs with realtime on and with **per-model opt-out**: notifications are on globally and
  off for the ledger models `JournalEntry` and `JournalLine`, which are written as a side effect
  of invoices and bills.
- The ERP Docker compose file demonstrates **cross-worker fan-out**: two uvicorn workers plus a
  Redis service, with pub/sub and presence both on Redis.
- The hosted ERP demo has realtime on, single process and in-memory. Visitors can see it work
  with a second account (`demo2`), and can watch live updates arrive as a read-only user
  (`demo_ro`).
- The load-test stack keeps realtime **off**, so the stored baselines stay comparable.
- The qualification suite stays green with realtime on. A small E2E smoke test proves the demo
  wiring itself.

## Non-Goals

- No library changes. Everything here is example-app code, compose and Dockerfile changes, and
  documentation. Anything the demos reveal in the library is filed as a separate bug.
- No new realtime features (for example SSE notifications, or notifications on detail pages).
- No load test of WebSocket traffic. Locust doesn't open sockets; a realtime load profile is a
  separate story.
- No Redis on the hosted Render demo. It is a single free-plan process; in-memory is correct
  there.
- No changes to the other examples (`simple`, `sqlalchemy`, `byoa`).

## BDD Scenarios

```
Scenario: full-demo order list updates live for another user
  Given full-demo is running and alice and bob are signed in, in separate browsers, both on the Orders list
  When  alice edits order ORD-2 and saves
  Then  bob's Orders list re-fetches without a reload
  And   the ORD-2 row is highlighted in bob's browser

Scenario: full-demo shows a toast when another user creates an order
  Given alice and bob are both on the Orders list
  When  bob creates an order
  Then  alice sees a toast naming bob and the new order
  And   the pagination total on alice's list goes up by one

Scenario: full-demo model without opt-in stays static
  Given alice and bob are both on the Suppliers list
  When  alice edits a supplier
  Then  bob's Suppliers list does not change until he reloads

Scenario: full-demo viewer never subscribes to a model it cannot view
  Given viewer is signed in (view orders and invoices, no products)
  When  viewer opens the Orders list
  Then  the page subscribes to orders only
  And   no subscribe frame for product is ever sent

Scenario: full-demo presence on the order edit page
  Given alice is on the edit page of ORD-1
  When  bob opens the edit page of ORD-1
  Then  both browsers show the other user in the presence bar

Scenario: ERP ledger models are excluded
  Given the ERP app is running with realtime on
  When  a user creates an invoice, which also writes journal entries
  Then  subscribers on the Invoices list are notified
  And   subscribers on the Journal entries list are not

Scenario: ERP compose fans out across workers
  Given the ERP compose stack runs two uvicorn workers and Redis
  And   alice's socket is on worker 1 and bob's socket is on worker 2
  When  alice edits an invoice
  Then  bob's Invoices list re-fetches

Scenario: hosted demo visitors see each other's changes
  Given the hosted demo seeds two accounts, demo and demo2, with the same permissions
  And   the login page names both accounts
  When  a visitor signed in as demo edits a contact while another window, signed in as demo2, shows the Contacts list
  Then  the demo2 window re-fetches and shows the highlighted row

Scenario: hosted demo read-only account receives live updates
  Given the hosted demo seeds demo_ro with only the view permissions of the ERP models
  And   a demo_ro window shows the Invoices list
  When  a visitor signed in as demo edits an invoice
  Then  the demo_ro window re-fetches and shows the highlighted row
  And   the demo_ro window shows no create, edit or delete controls

Scenario: load-test stack runs without realtime
  Given docker-compose.loadtest.yml sets DEMO_REALTIME=0
  When  the stack starts
  Then  Admin is built with realtime=None
  And   no WebSocket route is registered

Scenario: realtime can be turned off in either demo
  Given DEMO_REALTIME=0 is set in the environment
  When  full-demo or ERP starts
  Then  the app behaves exactly as it does today
```

## Design

### Architecture

Only example apps, deploy files and docs change. The examples consume the public API from
`hyperadmin` (`RealtimeSettings`, `AdminOptions.realtime_notifications`).

```
examples/full-demo/main.py ──▶ Admin(realtime=_realtime_settings())   (in-memory, single process)
examples/full-demo/admins.py ─▶ AdminOptions(realtime_notifications=True) on Order, Product

examples/erp/main.py ─────────▶ Admin(realtime=_realtime_settings())   REDIS_URL ⇒ Redis pub/sub + presence
examples/erp/accounting/admin.py ▶ AdminOptions(realtime_notifications=False) on JournalEntry, JournalLine
examples/erp/seed.py ─────────▶ seed_demo_user() also seeds demo2 and demo_ro (hosted demo only)
examples/erp/docker-compose.yml ▶ + redis service, 2 workers, REDIS_URL
docker-compose.loadtest.yml ──▶ DEMO_REALTIME=0 on the app service
deploy/demo/Dockerfile ───────▶ unchanged (realtime is on by default; no REDIS_URL ⇒ in-memory)
```

Each app gets a small private helper in its `main.py`:

```python
def _realtime_settings() -> RealtimeSettings | None:
    """Realtime on by default; DEMO_REALTIME=0 turns it off, REDIS_URL moves it to Redis."""
    if os.environ.get("DEMO_REALTIME", "1") == "0":
        return None
    redis_url = os.environ.get("REDIS_URL")
    return RealtimeSettings(
        notifications=False,  # full-demo only: opt-in per model; ERP keeps the default True
        pubsub_redis_url=redis_url,
        presence_redis_url=redis_url,
        enable_test_endpoints=bool(os.environ.get("E2E_TESTING")),
    )
```

The env names are deliberately not `HYPERADMIN_*`. That prefix belongs to `HyperAdminSettings`,
and these variables are example-app knobs, not library settings.

### full-demo

- `main.py`: `realtime=_realtime_settings()` with `notifications=False`.
- `admins.py`: `realtime_notifications=True` on `OrderAdmin` and `ProductAdmin`. `Supplier`,
  `Variant` and `Invoice` stay static, which shows the opt-in style. `OrderItem` is edited
  inline, so its changes reach subscribers as an `updated` event on the parent order.
- `README.md`: a new **Realtime** section with a two-browser walkthrough, one step per
  full-demo scenario above:
  - alice and bob on the Orders list;
  - the bulk *Archive* on several orders, which collapses into one summary toast;
  - viewer on the Orders list;
  - presence on ORD-1.

### ERP

- `main.py`: `realtime=_realtime_settings()` with the default `notifications=True`.
- `accounting/admin.py`: `realtime_notifications=False` on `JournalEntryAdmin` and
  `JournalLineAdmin`, which shows the opt-out style. Every other ERP model emits.
- `seed.py`: `seed_demo_user()` seeds two more accounts, both idempotent and both demo-mode
  only:
  - `demo2` / `demo2`: identical to `demo` (every permission except those on the built-in auth
    models).
  - `demo_ro` / `demo_ro`: only the `view_*` permissions of the ERP models. It shows permission
    gating (no create, edit or delete controls, and 403 on writes) while still receiving live
    updates, because it can view the lists.

  The new constants sit next to the existing `DEMO_USERNAME` / `DEMO_PASSWORD`. The account
  list is one tuple, `DEMO_ACCOUNTS`, with a username, a password and a permission filter per
  account.
  This is needed because the client hides feedback (toasts) for its own events: an event
  counts as its own when its `actor_id` matches the browser's user. Presence is keyed by user
  too. With a single shared `demo` account, two visitors would look like one user to each
  other. The extra accounts give a visitor a way to see the feature with several windows.
- `templates/login.html`: the login hint still prefills `demo` / `demo`. Below it, a short
  list names the other accounts: "demo2 / demo2, to watch live updates in a second window;
  demo_ro / demo_ro, read-only". `login_hint` stays a tuple, and the list is a new
  `login_hint_accounts` global, set only in demo mode.
- `docker-compose.yml`: add `redis:7-alpine` and `postgres:16` services. The app runs
  `uvicorn examples.erp.main:app --workers 2` with `REDIS_URL=redis://redis:6379/0`, so
  cross-worker fan-out is visible locally. Switching from `fastapi dev` to `uvicorn` drops
  reload, which this compose file (`ENVIRONMENT=production`) doesn't need. Local
  `uv run fastapi dev` stays single-process and in-memory.
  - The app gets `DATABASE_URL=postgresql://…@postgres:5432/erp`, mirroring
    `docker-compose.loadtest.yml`, with `depends_on` health checks on both services. Both
    workers run the startup lifespan, and ERP serialises it with `_startup_lock()` on
    PostgreSQL only, so SQLite with two workers would race on create and seed.
- `README.md`: a new **Realtime** section covering three ways to run it: local (one process,
  in-memory), compose (two workers and Redis), and the hosted demo (demo and demo2).
- `docker-compose.loadtest.yml`: add `DEMO_REALTIME: "0"` to the `app` service, a one-line
  hunk.

### Hosted demo (Render)

- `deploy/demo/Dockerfile` and `render.yaml` stay unchanged. Realtime is on because the
  default is on, and there is no `REDIS_URL`, so it runs in-memory in one process.
- The WebSocket `Origin` check compares `Origin` with `Host`. Uvicorn already runs with
  `--proxy-headers --forwarded-allow-ips '*'`, so the scheme and host are the public ones. If
  the first deploy logs "WebSocket Origin check failed", the fix is to add
  `HYPERADMIN_CSRF_TRUSTED_ORIGINS=https://<service>.onrender.com` to `render.yaml`. That is a
  configuration change, not a code change.

### E2E smoke

New file `tests/e2e/test_demo_realtime.py`, so neither `tests/e2e/conftest.py` nor
`test_qualification.py` changes. It reuses the `start_server` fixture, as `full_demo_base_url`
does, and boots `tests.e2e.apps.full_demo` with `E2E_TESTING=1`. It covers two scenarios with
two browser contexts:

- the live order list update;
- the static Suppliers list.

The other full-demo scenarios are library behaviour, which the #313 suite already covers. They
are checked by hand from the README walkthrough. The ERP and compose scenarios are checked by
hand too: CI has no Redis service for E2E, and adding one would be a CI-scope change that needs
its own PR.

### Data Model Changes

No data model changes. The ERP seed adds one row to `User` (and its permission rows) in demo
mode only.

### API / Protocol Changes

No API changes.

### Configuration Changes

No library configuration changes. Example-app environment variables:

| Variable | Apps | Default | Meaning |
|---|---|---|---|
| `DEMO_REALTIME` | full-demo, ERP | `1` | `0` builds `Admin(realtime=None)`. |
| `REDIS_URL` | full-demo, ERP | unset | Puts pub/sub and presence on Redis (`[redis]` extra). |

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| Qualification suite with sockets open | Ten checks now run with a live WebSocket on every page. Playwright's `networkidle` doesn't wait on WebSockets, but the 13 `networkidle` waits in `tests/e2e` are re-run with realtime on before merge. If any test turns flaky, `tests/e2e/apps/full_demo` sets `DEMO_REALTIME=0` for the qualification fixture and the smoke test opts in explicitly; that fallback is a decision-log change. |
| `REDIS_URL` set without the `[redis]` extra | `RedisPubSub` raises its existing "install hyper-admin[redis]" error on first use. The ERP Dockerfile runs `uv sync --all-extras`, so compose has the extra. The hosted Dockerfile does not, and it sets no `REDIS_URL`. |
| Redis down in compose | Publishing logs a warning and requests keep working (library behaviour). The README says so. |
| Shared login on the hosted demo | Covered by `demo2` and `demo_ro` (see ERP). Two windows on the same account still re-fetch, but show no toast, which is the documented "own changes" behaviour. |
| Render free plan spins down | The socket drops and the client's existing reconnect with backoff takes over when the service wakes. A nightly redeploy also drops sockets; same handling. |
| Two ERP workers on SQLite | Not supported in compose. Compose uses PostgreSQL (see ERP). |
| Load-test baselines | `DEMO_REALTIME=0` keeps the write path without the proxy, so `loadtest/baselines` stay comparable. |
| Seeding writes before routes exist | Seeding runs in the lifespan through the ORM, not through adapters, so it emits nothing. |
| `viewer` in full-demo | Without `view_product`, viewer never gets the Products hook (the notifications SDD's first permission check). This doubles as a manual permission demo. |

## Migration & Backward Compatibility

Backward compatible; no migration required. This only changes example apps. Anyone running
the examples gets realtime by default and can turn it off with `DEMO_REALTIME=0`.

## Delivery Plan

Two stories touch disjoint files, so they can run in parallel. Both depend on #312, so the
README walkthroughs describe behaviour that is visible.

| Story | Files to change | Blocked by |
|---|---|---|
| **#784: full-demo realtime** | `examples/full-demo/main.py`, `examples/full-demo/admins.py`, `examples/full-demo/README.md`, `tests/e2e/test_demo_realtime.py` (new) | #312 (and #313 for the shared E2E helpers, if any) |
| **#785: ERP realtime** | `examples/erp/main.py`, `examples/erp/accounting/admin.py`, `examples/erp/seed.py`, `examples/erp/templates/login.html`, `examples/erp/docker-compose.yml`, `examples/erp/README.md`, `docker-compose.loadtest.yml` (one line) | #312 |

Each story is one PR, with the test commit first where a test exists. Manual test scenarios go
in the PR body, following the scenarios above. Story B's PR description lists the Render
check: after the first deploy, open three windows (demo, demo2 and demo_ro) and confirm the live
update in the other two.

## Open Questions

All resolved by the owner on 2026-11-01:

1. **Shared hosted account.** Seed `demo2` **and** a read-only `demo_ro`.
2. **ERP compose database.** Switch compose to PostgreSQL.
3. **Ship before #312?** No. Both stories wait for #312.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| full-demo opts in (`notifications=False` plus two models), ERP opts out (two ledger models off) | The two demos show both configuration styles from the notifications SDD. | Both default-on (shows only one style); both opt-in (ERP's many models would need many flags). |
| Env vars `DEMO_REALTIME` and `REDIS_URL`, not `HYPERADMIN_*` | They are example knobs. A `HYPERADMIN_` name would look like a library setting. | Library-level env support for realtime (a new feature and out of scope). |
| Realtime off in the load-test stack | Keeps the stored baselines comparable. A WebSocket load profile is its own story. | Realtime on with Redis in the load test (changes what the baselines measure). |
| New `tests/e2e/test_demo_realtime.py` | Avoids the `tests/e2e/conftest.py` hotspot and keeps `test_qualification.py` about H2–H20. | A new H-row in the qualification suite (mixes realtime into upstream-readiness). |
| Hosted demo stays in-memory | One free-plan process; Redis would add a paid service for no visible gain. | A Render Key Value instance (cost, and it isn't needed for a single process). |
| Seed `demo2` and `demo_ro` on the hosted demo | Visitors share `demo`, so a second account is needed to see toasts and presence; `demo_ro` shows live updates reaching a read-only user. | Accept one shared account (toasts and presence look like one user); per-visitor sign-up (out of scope). |
| ERP compose on PostgreSQL with two workers and Redis | Startup is serialised only on PostgreSQL, and this is the one place the Redis path can be seen. | SQLite with one worker (no cross-worker demo). |
| Both stories wait for #312 | READMEs describe behaviour that is visible from day one. | Ship full-demo now with presence only. |
