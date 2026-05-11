# SDD: Multi-Tenancy Filtering

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #421 (epic) |
| Milestone | v0.5.3 — Multi-Tenancy Filtering |
| Created | 2026-05-10 |
| Last updated | 2026-05-10 |

---

## Problem

HyperAdmin v0.5.1 shipped the `BaseAdapter.get_queryset()` hook (a per-request `dict[str, Any]`
filter merged into list/get/count queries) and `ObjectPermissionChecker` (per-object authorization).
Both are foundational seams; neither is wired into a concrete tenant-isolation flow.

Real deployments need:

1. **List/detail isolation.** A user belonging to tenant `T1` must not see rows for tenant `T2`,
   even if they hold the model-level `view_X` permission. Pagination counts must reflect the
   tenant-filtered total.
2. **Tenant resolution.** The tenant id must be resolved per-request from a stable source
   (user record, request header, or subdomain) and exposed as `request.state.tenant_id`.
3. **Configuration.** Per-`ModelAdmin` opt-in (`tenant_field`) and a global enable flag
   (`tenant_enabled`) so single-tenant apps see no behaviour change.
4. **Adapter ergonomics.** A drop-in `TenantAwareAdapterMixin` lets adapters participate in
   tenant filtering without each one re-implementing the merge with `get_queryset()`.

Without this milestone, the v0.5.1 row-level-security hook is academic — it exists, but no
shipping component uses it. v0.5.4 (Dashboard) and v0.6.0 (real-time channels) both depend on
"current tenant" being a request-scoped concept.

## Goals

- `TenantAwareAdapterMixin` injects a tenant filter into `get_queryset()` automatically,
  reading `request.state.tenant_id` and applying `{tenant_field: tenant_id}`.
- `TenantMiddleware` resolves the tenant id from (in order): authenticated user's tenant
  attribute → `X-Tenant-ID` header (only honoured when the user is configured with
  `is_multi_tenant_admin=True`) → request subdomain (when `tenant_resolve_from_subdomain=True`).
- `AdminOptions.tenant_field: str | None = None` declares the column name on the model
  carrying the tenant id. None ⇒ this `ModelAdmin` is tenant-agnostic.
- `HyperAdminSettings.tenant_enabled: bool = False` is the kill switch. Disabled ⇒ middleware
  short-circuits, mixin is a no-op, no behaviour change for existing apps.
- Superuser bypass is opt-in per `AdminOptions.tenant_superuser_bypass: bool = True` (default
  `True` to match Django expectations; can be disabled for stricter deployments).
- 404 (not 403) on cross-tenant `get(pk)` to avoid disclosing existence.
- Documentation patterns for the three deployment shapes (single-tenant, multi-tenant
  same-DB, sharded) and the OAuth-bridge story for v0.5.2.

## Non-Goals

- Schema-per-tenant or DB-per-tenant — both are deployment patterns the host app owns; the
  framework supports them via custom `BaseAdapter` subclasses but does not ship one.
- Tenant CRUD UI / tenant onboarding wizard — host application concern.
- Tenant-scoped RBAC (per-tenant permission grants) — defer; v0.5.1 model-level + object-level
  is sufficient.
- Cross-tenant administrative views ("list rows from all tenants") beyond a `superuser`
  bypass — out of scope.
- Tenant-aware caching / connection pooling — performance milestone (v0.7.x).
- Tenant resolution from JWT claims — covered in v0.5.2 OAuth SDD via the `tenant_id_claim`
  hook on `OAuthProviderConfig`.

## BDD Scenarios

```
Scenario: tenant-aware adapter filters list results by request tenant
  Given Order.tenant_field = "tenant_id"
  And   request.state.tenant_id = 1
  And   the table contains orders with tenant_id in {1, 2, 3}
  When  GET /admin/order
  Then  the response lists only orders with tenant_id = 1
  And   pagination_info.total_count equals the tenant_id=1 row count

Scenario: cross-tenant detail returns 404 to prevent existence disclosure
  Given Order.tenant_field = "tenant_id"
  And   request.state.tenant_id = 1
  And   order#42 has tenant_id = 2
  When  GET /admin/order/42
  Then  the response is 404 Not Found
  And   no detail data is rendered

Scenario: cross-tenant update returns 404
  Given Order.tenant_field = "tenant_id"
  And   request.state.tenant_id = 1
  And   order#42 has tenant_id = 2
  When  POST /admin/order/42/edit with valid data
  Then  the response is 404 Not Found
  And   the row is unchanged

Scenario: superuser bypass is enabled by default
  Given a superuser request
  And   Order.tenant_field = "tenant_id"
  And   tenant_superuser_bypass is True
  When  GET /admin/order
  Then  the response lists orders for all tenants

Scenario: superuser bypass can be disabled per ModelAdmin
  Given a superuser request
  And   Order.tenant_field = "tenant_id"
  And   tenant_superuser_bypass is False
  When  GET /admin/order with no resolved tenant
  Then  the response is 400 Bad Request

Scenario: middleware resolves tenant from authenticated user
  Given user "alice" has tenant_id = 7 in the user store
  When  alice issues an authenticated request
  Then  request.state.tenant_id == 7

Scenario: header overrides user tenant only when admin opt-in is set
  Given user "alice" has tenant_id = 7
  And   alice.is_multi_tenant_admin is True
  When  alice issues a request with X-Tenant-ID: 9
  Then  request.state.tenant_id == 9

Scenario: header is ignored without opt-in
  Given user "alice" has tenant_id = 7
  And   alice.is_multi_tenant_admin is False
  When  alice issues a request with X-Tenant-ID: 9
  Then  request.state.tenant_id == 7

Scenario: subdomain resolution when configured
  Given tenant_resolve_from_subdomain is True
  And   the host map resolves "acme.example.com" → tenant_id 12
  When  a request arrives at https://acme.example.com/admin/
  Then  request.state.tenant_id == 12

Scenario: tenant_enabled=False short-circuits the middleware
  Given HyperAdminSettings.tenant_enabled is False
  When  any request arrives
  Then  request.state.tenant_id is unset
  And   list queries return all rows regardless of any tenant_field setting

Scenario: aggregate queries respect the tenant filter
  Given Order.tenant_field = "tenant_id"
  And   request.state.tenant_id = 1
  When  the dashboard count widget invokes adapter.count()
  Then  the count reflects only tenant_id = 1 rows

Scenario: missing tenant_id on a tenant-scoped model raises a clear error
  Given Order.tenant_field = "tenant_id"
  And   the request has no resolved tenant_id (anonymous, tenant_enabled=True)
  When  GET /admin/order
  Then  the response is 400 Bad Request with body "tenant required for /admin/order"
```

## Design

### Architecture

```
HTTP request
    │
    ▼
AuthenticationMiddleware  ──────► request.state.user
    │
    ▼
TenantMiddleware          ──────► request.state.tenant_id
    │                              (None if disabled / unresolved)
    ▼
View handler invokes adapter.list/get/count
    │
    ▼
TenantAwareAdapterMixin.get_queryset(request)
    │   reads options.tenant_field + request.state.tenant_id
    ▼
{tenant_field: tenant_id} merged into adapter's WHERE clause
    │   (existing v0.5.1 path)
    ▼
SQL: WHERE tenant_id = :tid AND <other filters>
```

Module layout (new files marked `(new)`, modified files marked `(mod)`):

```
src/hyperadmin/
├── auth/
│   └── tenant.py           (new) — TenantMiddleware, resolution helpers
├── adapters/
│   ├── tenant.py           (new) — TenantAwareAdapterMixin
│   ├── sqlmodel.py         (mod) — list/get/count already merge get_queryset(); no change
│   └── sqlalchemy.py       (mod) — same
├── core/
│   ├── auth.py             (mod) — add Tenant protocol (lightweight, optional)
│   ├── options.py          (mod) — add tenant_field, tenant_superuser_bypass
│   └── settings.py         (mod) — add tenant_enabled, tenant_resolve_from_subdomain,
│                                  tenant_subdomain_resolver, tenant_id_attr
├── views/
│   └── dynamic.py          (mod) — get/update/delete return 404 on cross-tenant miss
└── tests/
    ├── unit/
    │   ├── test_tenant_middleware.py   (new)
    │   ├── test_tenant_mixin.py        (new)
    │   └── test_tenant_options.py      (new)
    └── e2e/
        └── test_multi_tenant_isolation.py (new)
```

Dependency direction stays inward: `auth/tenant.py` and `adapters/tenant.py` both depend on
`core/`, never the other way around. No new public coupling between `auth/` and `adapters/`.

### Data Model Changes

No new framework-owned tables. The host application owns its `Tenant` table (or none —
`tenant_id` may be a free-form string).

The framework's `User` model does **not** gain a `tenant_id` column. Instead, the tenant
attribute name is configurable:

```python
# HyperAdminSettings
tenant_id_attr: str = "tenant_id"
```

`TenantMiddleware` reads `getattr(request.state.user, settings.tenant_id_attr, None)`.
This lets host apps put the tenant association anywhere (column on User, FK to Tenant,
property derived from membership table).

### API / Protocol Changes

**New mixin** in `src/hyperadmin/adapters/tenant.py`:

```python
class TenantAwareAdapterMixin:
    """Inject {tenant_field: request.state.tenant_id} into get_queryset()."""

    options: AdminOptions  # provided by the concrete adapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        base = super().get_queryset(request)  # respects subclass overrides
        if request is None:
            return base
        tenant_field = self.options.tenant_field
        if not tenant_field:
            return base
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            user = getattr(request.state, "user", None)
            if user is not None and getattr(user, "is_superuser", False) \
               and self.options.tenant_superuser_bypass:
                return base  # superuser sees all tenants
            raise HTTPException(
                status_code=400,
                detail=f"tenant required for {request.url.path}",
            )
        return {**base, tenant_field: tenant_id}
```

The mixin is composed onto a concrete adapter when the host app wants tenant filtering:

```python
class TenantSQLModelAdapter(TenantAwareAdapterMixin, SQLModelAdapter):
    pass
```

Apps that prefer a one-liner can set `Admin(default_adapter=TenantSQLModelAdapter)`.

**New middleware** in `src/hyperadmin/auth/tenant.py`:

```python
class TenantMiddleware:
    def __init__(self, app: ASGIApp, settings: HyperAdminSettings) -> None: ...
    async def __call__(self, scope, receive, send) -> None:
        # 1. If tenant_enabled is False → no-op
        # 2. Resolve from user.<tenant_id_attr> by default
        # 3. If user.is_multi_tenant_admin → honour X-Tenant-ID header
        # 4. If settings.tenant_resolve_from_subdomain → resolve via host map
        # Set request.state.tenant_id
```

**View-layer 404-on-cross-tenant** lives inside `DynamicModelView.detail_view/update_view/
delete_action`. When `adapter.get(pk)` returns `None` and a tenant filter is active, the
existing 404 path already covers it — no new branch needed. The change is behavioural:
verify in tests that 404 (not 403) is returned.

**`AdminOptions` additions** in `src/hyperadmin/core/options.py`:

```python
tenant_field: str | None = None
tenant_superuser_bypass: bool = True
```

`__init__.py` exports gain `TenantAwareAdapterMixin` and `TenantMiddleware`.

### Configuration Changes

| Setting | Default | Description |
|---|---|---|
| `HYPERADMIN_TENANT_ENABLED` | `False` | Kill switch. Disabled ⇒ middleware no-op |
| `HYPERADMIN_TENANT_ID_ATTR` | `"tenant_id"` | Attribute name on `request.state.user` |
| `HYPERADMIN_TENANT_RESOLVE_FROM_SUBDOMAIN` | `False` | Enable subdomain → tenant lookup |
| `HYPERADMIN_TENANT_SUBDOMAIN_RESOLVER` | `None` | Dotted import path to `Callable[[str], int \| None]` |
| `HYPERADMIN_TENANT_HEADER_NAME` | `"X-Tenant-ID"` | Header name for cross-tenant admins |

Per-`ModelAdmin`:

```python
class OrderAdmin(ModelAdmin):
    options = AdminOptions(
        tenant_field="tenant_id",
        tenant_superuser_bypass=True,
    )
```

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `tenant_enabled=True` but request has no resolved tenant and user is not a superuser | 400 Bad Request with `"tenant required for {path}"` (early signal in development) |
| `tenant_field` set but model has no such column | SQL error surfaces during list() — fail loudly. Documented as developer error |
| Cross-tenant `get(pk)` | Returns `None` from adapter (filter excludes it); view raises 404 |
| Cross-tenant `update(pk, data)` | `update()` returns 0 rows; view raises 404 |
| Cross-tenant `delete(pk)` | Same as update — 404 |
| Aggregate / count queries | The same `get_queryset()` filter applies (already merged into count in v0.5.1) |
| Subdomain resolver raises | Caught; tenant left unresolved; log warning |
| Header-supplied tenant id is non-integer when DB column is integer | Coerce with `int()`; on `ValueError` → 400 |
| User has `is_superuser=True` but no tenant_id | Bypasses filter (superuser exception). Document as expected |
| Tenant filter + object-level checker disagree | Object-level checker runs after row is fetched (post-filter). If row passes tenant filter, then object check applies. Behaves like an AND |
| HTMX inline-cell-edit endpoint | Same protections — view fetches row via adapter.get(pk), tenant filter applies, 404 on cross-tenant |
| Adapter without the mixin | Behaves exactly as today — backward compatible |
| `selectinload` relationships pulling cross-tenant rows | Documented: secondary relations are not auto-filtered. Host adds query options or model-level filters |
| Bulk operations (future) | Inherit the same filter via `get_queryset()` — no new path needed |

## Migration & Backward Compatibility

- **No breaking changes.** All new fields default to `None` / `False`.
- **No DB migration.** `tenant_id` columns belong to the host application's models; the
  framework adds none.
- **Public API.** `__init__.py` gains `TenantAwareAdapterMixin` and `TenantMiddleware`. No
  removals or renames. Semver-minor bump.
- **Adapter contract.** `get_queryset()` signature unchanged. Mixin overrides via `super()`,
  so subclassing third-party adapters continues to work.

Recommended adoption path for existing apps:

1. Add `tenant_id` column to relevant models (host migration).
2. Set `HYPERADMIN_TENANT_ENABLED=true` and `tenant_id_attr` on user model.
3. Switch adapters to `TenantSQLModelAdapter` (or compose the mixin manually).
4. Set `tenant_field="tenant_id"` on each scoped `ModelAdmin`.
5. Verify `request.state.tenant_id` is populated; ship.

## Open Questions

- [x] Single global header name vs. per-`ModelAdmin`? → **Global.** Header name is an
      org-wide convention; per-model would invite drift.
- [x] Should the mixin auto-coerce `tenant_id` (e.g., string → int)? → **No.** Adapter
      column types differ (UUID, str, int). Host app's tenant resolver returns the right
      type.
- [x] Default `tenant_superuser_bypass` to `True` or `False`? → **`True`.** Matches Django
      and existing v0.5.1 superuser conventions; explicit opt-out is cheap.
- [x] 404 vs 403 on cross-tenant access? → **404.** 403 leaks existence ("this row exists
      but you can't see it"); 404 is opaque.
- [ ] Should `TenantMiddleware` order be enforced relative to `AuthenticationMiddleware`?
      → Yes — `TenantMiddleware` must run **after** auth so `request.state.user` is set.
      Documented in `Admin.__init__` middleware stack registration. **Resolved on approval.**
- [ ] OAuth user provisioning (v0.5.2) sets `user.tenant_id` how? → Documented in the OAuth
      SDD. The `OAuthProviderConfig.tenant_id_claim` field maps a userinfo claim onto the
      user's tenant attribute. New users without a claim get `tenant_id=None` and are
      unreachable until an admin assigns them. **Resolved by reference to `oauth-sso.md`.**

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Mixin composition over inheritance | Composable with any adapter (SQLModel, SQLAlchemy, third-party) without changing the base contract | Make `BaseAdapter` always tenant-aware — breaks existing adapters and forces a config flag everywhere |
| Tenant id attribute is a settings-driven name (`tenant_id_attr`) | Host apps embed tenancy in many shapes (column, FK, derived property); we should not prescribe one | Hard-code `user.tenant_id` — couples framework to host schema |
| Tenant resolution prefers user → header → subdomain | User attribute is the safest default; header is an explicit cross-tenant admin opt-in; subdomain is for B2B SaaS with vanity URLs | URL-prefix routing (`/t/{tid}/...`) — breaks all existing URL helpers |
| 404 on cross-tenant miss | Prevents existence disclosure | 403 — leaks information; rejected |
| Settings kill switch (`tenant_enabled`) | Existing single-tenant apps must see zero behavioural change after the upgrade | No flag — every install would have to opt out, hostile to upgrade path |
| Superuser bypass on by default | Mirrors Django; admin tools need it | Default-off — surprising for users coming from Django |
| Filter is a flat `dict[tenant_field, tenant_id]` | Consistent with v0.5.1 `get_queryset()` shape; no `Select` mutator coupling | Callable filter — too flexible, harder to reason about; defer to v0.5.3+ if needed |
| No new table for tenant ↔ user mapping | Host apps already have this; framework would duplicate / conflict | Ship a `Tenant` table — out of scope, opinionated |
