# Full-demo umbrella app

One HyperAdmin app that exercises every upstream-readiness capability (H2–H20) with
framework-neutral models: `Supplier`, `Variant`, `Product`, `Order`, `OrderItem`, `Invoice`.
The per-feature apps under `examples/` stay as they are; this one shows the features working
together and is the target of the qualification suite.

## Boot

```bash
uv sync --all-extras
uv run examples/full-demo/main.py      # http://127.0.0.1:8000/admin
```

Sign in as `alice` / `secret123` (superuser). Also seeded: `bob` (superuser) and `viewer`
(password `secret123`, group `Viewers`: view and change orders, view invoices). The first run
creates `examples/full-demo/full_demo.db` next to `main.py`; delete it to start over.

## What to look at

| Capability | Where |
|---|---|
| H2 inline rows, per-row error highlight | Orders → edit ORD-1, set an item quantity to 0 |
| H3 bulk action, per-row outcome | Orders → select all → *Archive* (locked ORD-3 fails) |
| H4 detail panels, PDF | Orders → ORD-1 → Invoice / History / Transitions tabs |
| H5 `IsOwnerFilter` | Orders → sidebar → *Mine only* |
| H6 dependent FK + "+" popup | Products → create |
| H12 filter sidebar, saved views | Orders → sidebar (date range, supplier, paid) → *Save view* |
| H13 image upload thumbnail | Products → create with a cover image (list thumbnails: pending) |
| H14 OLAP report, CSV / XLSX | Reports → Sales by SKU → period switch, Export |
| H15 chart bound to the report | same page, chart above the grid |
| H20 permission matrix | Permissions matrix → *Viewers* → untick *change order* |

## Realtime

Live CRUD notifications and presence are on, with **per-model opt-in**: notifications are off
globally (`RealtimeSettings(notifications=False)`) and only `Order` and `Product` opt in with
`realtime_notifications=True`. `Supplier`, `Variant` and `Invoice` stay static. Everything runs
in one process on the in-memory backend. Try it with two browsers (or one normal and one
private window), one signed in as `alice` and one as `bob` (both `secret123`):

1. **Live list update.** Both open *Orders*. alice opens ORD-2, changes *Status* to
   `delivered` and saves. bob's list shows the new status without a reload, and the ORD-2 row
   flashes briefly.
2. **Toast on create.** Both stay on *Orders*. bob clicks *Create New* (number `ORD-6`, any
   date) and saves. alice sees a toast naming bob and the new order, and her pagination total
   goes up by one. bob sees no toast for his own change.
3. **Bulk action, one toast.** bob selects all rows on the list and runs *Archive*. alice sees
   one summary toast for the batch rather than one per row (locked ORD-3 still fails for bob).
4. **No opt-in, no live updates.** Both open *Suppliers*. alice edits a supplier and saves.
   bob's list does not change until he reloads.
5. **Viewer subscribes only to what it can see.** Sign in as `viewer` and open *Orders*. In
   the browser dev tools (Network, WS), the socket only sends a subscribe frame for `order`;
   viewer has no product permission, so none is sent for `product`.
6. **Presence.** alice opens ORD-1 → *Edit*. bob opens the same page. Each browser shows the
   other user in the presence bar.

Switches (example-app variables, not `HYPERADMIN_*` settings):

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_REALTIME` | `1` | `0` builds `Admin(realtime=None)`: no socket, no toasts, no presence. |
| `REDIS_URL` | unset | Puts pub/sub and presence on Redis (needs the `[redis]` extra, already in `--all-extras`). |

## Qualification suite

```bash
uv run poe test:e2e:qualification
```

runs `tests/e2e/test_qualification.py`: ten Playwright checks, one per row above, each booting
this app on a throwaway database (`E2E_TESTING=1`) with realtime on. When all ten pass on `develop`, the
framework is upstream-ready. `test_h13_jpeg_upload_thumbnail` is `xfail(strict=True)` until
list/detail thumbnails ship; the marker is removed in that change.
