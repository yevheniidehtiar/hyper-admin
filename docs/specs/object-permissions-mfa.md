# SDD: Object-Level Permissions & MVP Email-OTP MFA

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #473 |
| Milestone | v0.5.1 — Object Permissions & MFA |
| Created | 2026-05-03 |
| Last updated | 2026-05-03 |

---

## Problem

HyperAdmin today enforces only **model-level** permissions (`view_order`, `change_order`,
`delete_order`). Two real-world admin requirements are not yet covered:

1. **Row-level security.** Multi-tenant SaaS, customer-portal, and "you can only see your own
   records" scenarios all require filtering and per-object checks. Today, a user who has the
   `view_order` permission can read every `Order` row, including rows belonging to other
   tenants/owners.
2. **Multi-factor authentication.** Production deployments expect at minimum a second factor for
   privileged accounts. HyperAdmin currently authenticates with username + password and nothing
   else; there is no second-factor seam in the login flow.

Without these, HyperAdmin is unsuitable for any deployment that handles tenant-scoped or
sensitive data — which is most of them. Object-level permissions also unblock the planned
multi-tenancy filtering work in v0.5.3 (it is a strict prerequisite).

## Goals

- Define an `ObjectPermissionChecker` protocol that adds per-object authorization to every
  `detail`, `update`, `delete`, and inline-cell-edit pathway, alongside the existing
  model-level `PermissionChecker`.
- Add a `get_queryset()` hook on adapters and `ModelAdmin` so list/detail queries can be
  filtered per-request before any view-layer filters run (row-level security).
- Add a minimal MVP MFA flow using **email-delivered 6-digit OTP**, slotted into the existing
  login flow without breaking single-factor logins.
- Allow each user to enable/disable MFA from a settings view.
- Stay **backward compatible**: defaults are no-ops; existing apps render and authenticate
  identically.

## Non-Goals

- TOTP / authenticator-app MFA, hardware keys, WebAuthn, SMS — explicitly deferred to a future
  milestone (the `mfa_method` field is forward-extensible but only `"email"` is wired now).
- Field-level permissions (per-attribute view/edit) — different abstraction; future work.
- Admin-side bulk MFA enforcement / policy ("require MFA for staff") — deferred; users
  self-enable in MVP.
- OAuth/SSO — owned by v0.5.2.
- Multi-tenancy *adapter mixins* (`TenantAwareAdapter`) — owned by v0.5.3. This SDD only delivers
  the `get_queryset()` seam that v0.5.3 will plug into.
- Audit-log persistence (CRUD diffs) — milestone description references it but it is out of
  scope here; deferred to its own SDD.

## BDD Scenarios

Aggregated from the v0.5.1 stories under
`.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/`. Story files remain the
canonical per-task spec; this section is the integration-level view.

### Track A — Object-Level Permissions & RLS

```
Scenario: ObjectPermissionChecker protocol is runtime-checkable
  Given a class implementing has_object_permission(user, obj, action) -> bool
  When  isinstance(instance, ObjectPermissionChecker) is evaluated
  Then  result is True

Scenario: default checker is permissive
  Given DefaultObjectPermissionChecker is used
  When  has_object_permission(user, obj, "view") is called
  Then  result is True

Scenario: get_queryset filters list results
  Given adapter.get_queryset() returns {"owner_id": 1}
  When  adapter.list() is called
  Then  the SQL query includes WHERE owner_id = 1
  And   only matching rows are returned
  And   the count reflects the filtered total

Scenario: get_queryset filters get() results
  Given adapter.get_queryset() returns {"owner_id": 1}
  When  adapter.get(pk=5) is called for a row with owner_id=2
  Then  the result is None

Scenario: empty get_queryset is a no-op (backward compatible)
  Given adapter.get_queryset() returns {}
  When  adapter.list() is called
  Then  all records are returned

Scenario: staff cannot view another user's record when object permission denies
  Given user "bob" has view_order model permission
  And   ObjectPermissionChecker denies "bob" access to order#42
  When  GET /admin/order/42
  Then  the response is 403 Forbidden

Scenario: object permission check is enforced on update
  Given ObjectPermissionChecker denies "bob" change access to order#42
  When  POST /admin/order/42/edit with valid data
  Then  the response is 403 Forbidden

Scenario: object permission check is enforced on delete
  Given ObjectPermissionChecker denies "bob" delete access to order#42
  When  POST /admin/order/42/delete
  Then  the response is 403 Forbidden

Scenario: superuser bypasses object-level checks
  Given a superuser "admin"
  And   ObjectPermissionChecker would deny order#42 for everyone
  When  GET /admin/order/42
  Then  the response is 200 OK
```

### Track B — MVP Email-OTP MFA

```
Scenario: new user has MFA disabled by default
  Given a new User record is created
  When  the user fields are inspected
  Then  mfa_enabled is False and mfa_method is None

Scenario: MFA-disabled user logs in with one factor
  Given user "bob" has mfa_enabled=False
  When  POST /admin/login with correct credentials
  Then  a full session is created
  And   the response redirects to /admin/

Scenario: MFA-enabled user is redirected to challenge after password
  Given user "alice" has mfa_enabled=True
  When  POST /admin/login with correct credentials
  Then  a partial-auth session is created (no admin access)
  And   an OTP code is sent to alice's email
  And   the response redirects to /admin/mfa/challenge

Scenario: correct OTP code completes login
  Given alice is on the MFA challenge page with code "123456" pending
  When  POST /admin/mfa/verify with code=123456
  Then  the session is upgraded to full auth
  And   the response redirects to /admin/

Scenario: wrong OTP code shows an error
  Given alice is on the MFA challenge page
  When  POST /admin/mfa/verify with code=999999
  Then  the page re-renders with an "Invalid code" error
  And   the session remains partial-auth

Scenario: expired OTP code shows error with resend option
  Given alice's pending OTP code is older than the configured TTL
  When  POST /admin/mfa/verify with that code
  Then  the page re-renders with a "Code expired" error
  And   a "Resend code" link is shown

Scenario: rate limit blocks excessive OTP requests
  Given alice has requested 3 OTP codes in the last 10 minutes
  When  generate_and_send is called for alice again
  Then  RateLimitError is raised
  And   the UI surfaces a "Too many attempts, try later" message

Scenario: partial-auth session cannot reach admin routes
  Given alice has a partial-auth session
  When  she navigates to /admin/order
  Then  the response redirects to /admin/mfa/challenge

Scenario: enable MFA from settings
  Given alice is fully authenticated and visits /admin/mfa/settings
  When  she clicks "Enable MFA"
  Then  an OTP is sent and on successful verification mfa_enabled becomes True

Scenario: disable MFA from settings
  Given alice has mfa_enabled=True and visits /admin/mfa/settings
  When  she confirms "Disable MFA"
  Then  mfa_enabled becomes False
  And   the next login is single-factor
```

## Design

### Architecture

```
                      ┌─────────────────────────────────────┐
                      │          core/auth.py               │
                      │  Protocols (no ORM/HTTP deps)       │
                      │   - PermissionChecker  (existing)   │
                      │ + ObjectPermissionChecker  (NEW)    │
                      └─────────────────────────────────────┘
                              ▲                       ▲
                              │ implements            │ uses
                              │                       │
       ┌──────────────────────┴─────────┐     ┌───────┴────────────┐
       │   auth/permissions.py          │     │ core/options.py    │
       │  DefaultObjectPermissionChecker│     │ AdminOptions       │
       │  (permissive impl)             │     │ + object_permission│
       └────────────────────────────────┘     │   _checker field   │
                                              └────────────────────┘
                                                       ▲
                                                       │ injected
                                                       │
       ┌──────────────────────┐     ┌──────────────────┴──────────────┐
       │  core/adapters.py    │     │       views/dynamic.py          │
       │ + get_queryset()     │     │ _check_object_permission helper │
       └──────────┬───────────┘     │  detail / update / delete call  │
                  │                 └──────────┬──────────────────────┘
                  │ overridden in              │ called from
                  ▼                            │
       ┌──────────────────────┐                │
       │ adapters/sqlmodel.py │                │
       │ adapters/sqlalchemy  │  ◄─────────────┘  list() merges
       │  list() / get()      │                    queryset filters
       └──────────────────────┘

   ┌────────────────── Track B (MFA) ─────────────────────┐
   │                                                       │
   │  auth/models.py        auth/otp.py        auth/views.py
   │  + User.mfa_enabled    EmailOTPService    login_view (modified)
   │  + User.mfa_method     - generate_and_send + mfa_challenge_view
   │                        - verify           + mfa_verify_view
   │                        - rate_limit       + mfa_settings_view
   │                                                       │
   │  auth/middleware.py    templates/auth/                │
   │  + partial-auth gate   - mfa_challenge.html           │
   │                        - mfa_settings.html            │
   └───────────────────────────────────────────────────────┘
```

The two tracks are **independent**: Track A can ship without Track B and vice versa, but both
target the same milestone for delivery. Inside each track the layering follows the bottom-up
playbook (protocols → adapters/services → views → templates → tests).

### Data Model Changes

**Track A — none.** Object-level permissions are a runtime concern; no new tables.

**Track B — `User` model gets two additive fields:**

```python
# src/hyperadmin/auth/models.py
class User(SQLModel, table=True):
    ...
    mfa_enabled: bool = Field(default=False)
    mfa_method: str | None = Field(default=None, max_length=32)
```

`mfa_method` is `str | None` rather than an `Enum` to keep the surface forward-extensible
without a breaking migration when TOTP/SMS arrive in a later milestone. Validation that the
value is one of the allowed methods lives in the service layer.

**OTP storage:** session-scoped, **not** a new table. Codes are stored in the request session
under `state["mfa_otp"] = {"code_hash": ..., "issued_at": ..., "attempts": int}`.
Cleared on successful verification, on session destruction, and on TTL expiry. Hashing uses
the existing password-hash helper to keep raw codes out of session storage.

### API / Protocol Changes

**New protocol** in `src/hyperadmin/core/auth.py`:

```python
@runtime_checkable
class ObjectPermissionChecker(Protocol):
    async def has_object_permission(
        self, user: Any, obj: Any, action: str
    ) -> bool: ...
```

`action` uses the same codenames as `PermissionChecker`: `"view"`, `"add"`, `"change"`,
`"delete"`. Default implementation (`DefaultObjectPermissionChecker`) returns `True` for all
inputs. Superuser bypass is the implementation's responsibility, not the protocol's.

**New adapter hook** on `BaseAdapter`:

```python
def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
    """Return additional filters merged into list() and get() queries."""
    return {}
```

`SQLModelAdapter.list()` and `.get()` merge `get_queryset()`'s dict into their `WHERE` clause
**before** any view-layer filters. The same applies to the count query so pagination is
consistent. `SQLAlchemyAdapter` mirrors this behaviour.

**View-layer helper** added to `DynamicModelView` (`src/hyperadmin/views/dynamic.py`):

```python
async def _check_object_permission(
    self, request: Request, obj: Any, action: str
) -> None:
    checker = self.options.object_permission_checker
    if checker is None:
        return
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=403)
    if not await checker.has_object_permission(user, obj, action):
        raise HTTPException(status_code=403, detail="Permission denied")
```

Called from `detail_view`, `update_view`, and `delete_action` after the object is fetched.

**MFA service** in `src/hyperadmin/auth/otp.py`:

```python
class EmailOTPService:
    def __init__(
        self,
        email_sender: Callable[[str, str], Awaitable[None]],
        ttl_seconds: int = 300,
        rate_limit: tuple[int, int] = (3, 600),  # (max_codes, window_seconds)
    ) -> None: ...

    async def generate_and_send(self, user: User, session: dict) -> None: ...
    async def verify(self, user: User, code: str, session: dict) -> bool: ...
```

**MFA endpoints** added to `src/hyperadmin/auth/views.py`:

| Method | Path | Purpose |
|---|---|---|
| GET  | `/admin/mfa/challenge` | Render challenge form |
| POST | `/admin/mfa/verify`    | Verify OTP, upgrade session |
| POST | `/admin/mfa/resend`    | Re-issue OTP (rate-limited) |
| GET  | `/admin/mfa/settings`  | Render enable/disable view |
| POST | `/admin/mfa/enable`    | Begin enable flow (sends OTP) |
| POST | `/admin/mfa/disable`   | Disable MFA (requires confirmation) |

`login_view` is modified to: if password is correct AND `user.mfa_enabled`, write
`request.session["partial_auth_user_id"] = user.id`, do **not** call `auth_backend.login()`,
trigger `EmailOTPService.generate_and_send()`, and redirect to `/admin/mfa/challenge`.

`AuthMiddleware` (or a new lightweight gate inside it) treats partial-auth sessions as
unauthenticated for `/admin/*` routes other than the MFA endpoints, redirecting to
`/admin/mfa/challenge`.

### Configuration Changes

New fields on `AdminOptions` (per-`ModelAdmin`):

```python
object_permission_checker: ObjectPermissionChecker | None = None
```

New fields on `HyperAdminSettings` (global, env-driven):

```python
mfa_otp_ttl_seconds: int = 300
mfa_otp_rate_limit: tuple[int, int] = (3, 600)
mfa_email_sender: str | None = None  # dotted import path; resolved at startup
```

`Admin.__init__` resolves `mfa_email_sender` and constructs an `EmailOTPService` if MFA is
configured. Apps that do not set `mfa_email_sender` see no behavioural change — MFA simply
remains unreachable, and `mfa_enabled=True` users will be redirected to a challenge that
returns 503 with a clear "MFA misconfigured" message (caught at startup with a warning,
not a hard error, to keep dev ergonomics).

### Tests

- **Unit:** `tests/unit/test_object_permissions.py`, `tests/unit/test_get_queryset.py`,
  `tests/unit/test_email_otp_service.py`, `tests/unit/test_mfa_login_flow.py`
- **E2E:** `tests/e2e/test_object_permissions.py`, `tests/e2e/test_mfa_login.py`
  - Each Playwright test maps 1:1 to a BDD scenario above with inline
    `# Given / # When / # Then` comments.
  - Locators use `get_by_role` / `get_by_label` / `data-testid` per CLAUDE.md.
  - New `data-testid` values: `mfa-code-input`, `mfa-verify-btn`, `mfa-resend-link`,
    `mfa-enable-btn`, `mfa-disable-btn`.

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `object_permission_checker` is `None` | Helper is a no-op; behaves as today (model-level only). |
| `request.state.user` is missing on a permission-checked route | Raise 403 — protected routes always require an authenticated user. |
| `get_queryset()` returns a non-dict | Treat as developer error: raise `TypeError` early so misconfig surfaces in tests, not in production silence. |
| Concurrent `get_queryset()` evaluation across threads | Filter dict is re-evaluated per request; no shared mutable state. Tenant filter callables must be pure / request-scoped — documented in the adapter docstring. |
| Count query with `get_queryset()` filter | Filters are merged into both list and count queries so pagination math stays correct. |
| OTP storage on stateless deployments | Sessions already require a session backend; OTP rides on top. Documented as a hard requirement. |
| User clears cookies mid-MFA challenge | Partial-auth session lost → next request is treated as anonymous → user is sent back to `/admin/login`. No half-state leak. |
| Two browser tabs, one in challenge / one in login | Latest `generate_and_send` overwrites prior OTP in session; older code becomes invalid (single active code per user). |
| Rate limit exceeded | `EmailOTPService.generate_and_send` raises `RateLimitError`; views catch and render a localized "Too many attempts, try later" message. Login view does **not** rotate the partial-auth session — user can resume after the cooldown. |
| Email send failure | Rolls back the OTP store and surfaces a 502 with retry guidance; partial-auth session is cleared so the user is not stranded. |
| Disable-MFA without re-authentication | Disable flow requires a fresh OTP confirmation (defense in depth) — clicking "Disable" sends a new code; submitting it flips `mfa_enabled=False`. |
| Superuser bypass | Lives in the `DefaultObjectPermissionChecker` reference impl, not the protocol — applications can opt out by providing their own checker. |
| Existing apps with `auth_backend` but no MFA | Untouched: `mfa_enabled=False` short-circuits the new code path entirely. |

## Migration & Backward Compatibility

- **No breaking changes.** Both tracks are purely additive.
- **No DB migration required** under SQLModel's "additive columns with defaults" rule. The two
  new `User` columns have defaults; existing rows are read with `mfa_enabled=False` /
  `mfa_method=None` as soon as the column is added by Alembic in app code (apps own their
  migrations). We document the column additions in the v0.5.1 changelog as a recommended
  migration step but do not auto-generate one.
- **Public API stability:** `__init__.py` exports gain `ObjectPermissionChecker` and
  `EmailOTPService`. Nothing is renamed or removed. No semver-major bump required.
- **Adapter contract:** `BaseAdapter.get_queryset()` lands with a default implementation, so
  third-party adapters keep working without changes — they only need to override if they want
  to participate in row-level filtering.

## Open Questions

- [ ] **OTP transport abstraction.** `email_sender` is a `Callable` for MVP. Do we want a thin
      `OTPTransport` protocol now (cheap, future-proofs SMS / push) or defer until a second
      transport actually exists? **Proposal:** defer — YAGNI; one callable is fine for MVP.
- [ ] **Partial-auth session shape.** Store `partial_auth_user_id` directly, or wrap it in a
      structured `auth_state` dict (`{"stage": "mfa_pending", "user_id": ...}`)? Structured
      form is more extensible (recovery flow, password reset). **Proposal:** structured dict
      from day one — small upfront cost, avoids a session migration later.
- [ ] **Rate limit storage.** Per-user counter lives in session (single-process safe) or in
      a shared store (Redis / DB) for multi-worker deployments? **Proposal:** session for MVP,
      document the multi-worker caveat, plan a pluggable counter for v0.6+.
- [ ] **`get_queryset()` signature: dict-of-filters vs. SQLAlchemy `Select` mutator?**
      Dict is simpler, declarative, and matches the existing filter-dict pattern in adapters.
      A `Select` mutator is more powerful (joins, subqueries) but couples `BaseAdapter` to
      SQLAlchemy. **Proposal:** ship dict in v0.5.1; introduce an optional
      `apply_queryset_filter(stmt) -> stmt` overload in v0.5.3 multi-tenancy work where
      richer filters are needed.

These must be settled (or explicitly deferred) before Status → Approved.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Email-OTP for MVP MFA | Zero new infra dependency (uses existing email_sender pattern); covers ~80% of admin-MFA use cases; sets up the seam for TOTP later. | TOTP first (better UX, but requires seed-management UI + QR rendering) |
| Filter dict for `get_queryset()` | Matches existing adapter filter-dict idiom; keeps `BaseAdapter` ORM-agnostic. | `Select` mutator (richer, but couples core to SQLAlchemy) |
| OTP stored in session, not a table | Avoids schema migration + cleanup job; OTPs are intrinsically short-lived; session backend is already required. | Dedicated `OTPCode` table (more durable but heavier; deferred) |
| Tracks A and B share one milestone | Both block real deployments; shipping together lets users adopt RLS + MFA in one upgrade. | Split into v0.5.1 / v0.5.2 (delays MFA; OAuth already owns v0.5.2) |
| Default checker is permissive (`True`) | Backward compatibility — apps that don't opt in see no behavioural change. | Default-deny (safer but breaks every existing install) |
| Partial-auth gate lives in middleware | Single chokepoint; cannot be bypassed by a forgotten check on a new view. | Per-view decorator (easier to drop on a route by accident) |
| Two duplicate adapter stories (#426, #478) | **Cleanup item.** Stories `featadapters-add-getqueryset-hook-to-baseadapter.md` and `featadapters-add-getqueryset-hook-to-baseadapter-sqlmodelada.md` both describe the same work; #478 supersedes #426 with explicit SQLModelAdapter scope. Resolve in pre-implementation triage by closing #426 as duplicate. | Keep both (causes split work / merge conflicts) |
