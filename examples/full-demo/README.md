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

## Qualification suite

```bash
uv run poe test:e2e:qualification
```

runs `tests/e2e/test_qualification.py`: ten Playwright checks, one per row above, each booting
this app on a throwaway database (`E2E_TESTING=1`). When all ten pass on `develop`, the
framework is upstream-ready. `test_h13_jpeg_upload_thumbnail` is `xfail(strict=True)` until
list/detail thumbnails ship; the marker is removed in that change.
