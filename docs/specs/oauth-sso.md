# SDD: OAuth2/OIDC SSO — Google & GitHub

| Field | Value |
|---|---|
| Author | Claude Code |
| Status | Draft |
| Issue | #420 (epic), #438 (review gate) |
| Milestone | v0.5.2 — OAuth SSO |
| Created | 2026-05-10 |
| Last updated | 2026-05-10 |

---

## Problem

HyperAdmin authenticates with username + password through `auth/views.py` and an
`AuthBackend` Protocol. v0.5.1 added MFA on top, so the existing flow is already
multi-stage. What is missing is **federated identity** — the ability to log in with
Google Workspace, GitHub, or another OIDC-conformant identity provider.

This blocks adoption by:

- Organizations whose security policy forbids holding password material outside their IdP.
- Engineering teams that already federate everything through GitHub.
- B2B SaaS hosts that want their customers' employees to sign in via the customer's IdP.

The existing local-auth path must keep working unchanged; OAuth must compose with MFA
(an OAuth login still triggers the local OTP step when `mfa_enabled=True`); and OAuth
must not undermine the v0.5.3 multi-tenancy work — tokens, claims, and provisioning rules
must all carry the tenant correctly.

## Goals

- **Two providers shipped:** Google (OIDC) and GitHub (OAuth2 + custom userinfo). Both via
  a generic `OAuthBackend` parameterized by `OAuthProviderConfig` so a third provider
  needs only configuration, not code.
- **Persistent tokens.** `OAuthToken` SQLModel stores per-user-per-provider access /
  refresh tokens, scopes, and expiry. Tokens are encrypted at rest with `cryptography.Fernet`
  using a key from `HYPERADMIN_OAUTH_TOKEN_SECRET` (32-byte url-safe base64).
- **Refresh middleware.** A lightweight middleware refreshes tokens that expire within
  the next 60 seconds and clears the session on hard refresh failure.
- **Account-linking policy.** First-time OAuth login with an email matching an existing
  local user does **not** auto-link. The user is told "Account exists; sign in with your
  password and link from settings." Linking only happens from an authenticated session.
- **MFA bridge.** OAuth login still respects `user.mfa_enabled`; the OAuth callback creates
  a partial-auth session and redirects to `/admin/mfa/challenge`.
- **Tenant bridge (v0.5.3 forward-compat).** `OAuthProviderConfig.tenant_id_claim`
  optionally maps a userinfo claim (e.g. Google `hd`) to the user's tenant attribute on
  provisioning. Without a mapping, new OAuth users get `tenant_id=None`.
- **Login page UI.** "Sign in with Google" / "Sign in with GitHub" buttons render only
  when the corresponding provider is configured.
- **PKCE.** All OAuth2 authorization-code flows use PKCE (`S256`). Public clients become
  optional later; PKCE in a server-side admin is cheap insurance against a leaked
  `client_secret`.
- **Backward compatible.** Apps with no OAuth configured see zero new UI, zero new tables
  used, zero behaviour change.

## Non-Goals

- SAML2 — different protocol family, requires XML signing; deferred indefinitely.
- Social-login providers beyond Google/GitHub (Microsoft, Okta, Auth0, Apple, ...) —
  shipped post-v0.5.2 by configuration only, no code.
- Provider-initiated logout / RP-initiated logout (OIDC end_session_endpoint) — defer.
- Session revocation endpoints — defer.
- Device-authorization grant (CLI flow) — defer.
- Token introspection / userinfo polling for live group membership — defer.
- SSO-driven group membership sync (claims → permissions) — defer to a later milestone;
  v0.5.2 only provisions a base User row.
- An admin UI to register / configure OAuth providers — host app passes config in code.

## BDD Scenarios

```
Scenario: login page shows OAuth buttons only for configured providers
  Given Admin is configured with provider "google"
  And   provider "github" is NOT configured
  When  the user navigates to /admin/login
  Then  the page shows a "Sign in with Google" button
  And   the page does NOT show a "Sign in with GitHub" button

Scenario: clicking the provider button redirects to authorize URL with PKCE
  Given Admin is configured with provider "google"
  When  the user clicks "Sign in with Google"
  Then  the response is 302 to https://accounts.google.com/o/oauth2/v2/auth?...
  And   the URL includes code_challenge and code_challenge_method=S256
  And   request.session contains the matching code_verifier and state nonce

Scenario: callback exchanges code for tokens and provisions a new user
  Given Admin is configured with provider "google"
  And   the IdP returns userinfo {"email": "alice@acme.com", "sub": "abc123"}
  And   no local user exists with that email
  When  GET /oauth/callback/google?code=...&state=<valid-state>
  Then  a new User row is created with email "alice@acme.com"
  And   an OAuthToken row stores the encrypted access and refresh tokens
  And   a full session is created
  And   the response redirects to /admin/

Scenario: callback links a returning user
  Given a User exists with provider="google" sub="abc123"
  When  GET /oauth/callback/google?code=...&state=<valid-state> with the same sub
  Then  no new User row is created
  And   the existing OAuthToken row is updated with new access / refresh values
  And   a full session is created

Scenario: callback with email matching a local-only user does NOT auto-link
  Given a local User exists with email "alice@acme.com" and no OAuthToken
  When  GET /oauth/callback/google with userinfo email="alice@acme.com"
  Then  the response is 409 Conflict
  And   the page renders "Account exists. Sign in with your password and link from settings."
  And   no User or OAuthToken rows are created

Scenario: callback rejects mismatched state nonce (CSRF protection)
  Given the session has state="abc"
  When  GET /oauth/callback/google?state=xyz&code=...
  Then  the response is 400 Bad Request
  And   no token exchange is attempted

Scenario: callback rejects expired state (10-minute TTL)
  Given the session-stored state was issued 11 minutes ago
  When  the OAuth callback arrives with that state
  Then  the response is 400 Bad Request

Scenario: provider error from IdP surfaces a clear message
  Given the IdP returns ?error=access_denied
  When  the user is redirected back to /oauth/callback/google
  Then  the response is 400 Bad Request
  And   the body contains "OAuth provider denied access"

Scenario: token refresh middleware refreshes near-expiry tokens
  Given alice has an OAuthToken with expires_at in 30 seconds
  When  alice issues an authenticated request
  Then  the middleware exchanges the refresh_token for a new access token
  And   the OAuthToken row is updated with the new access and expires_at
  And   the original request proceeds normally

Scenario: token refresh hard failure clears the session
  Given alice's refresh_token has been revoked at the IdP
  When  the middleware attempts a refresh and the IdP returns 400 invalid_grant
  Then  the user's session is cleared
  And   the response redirects to /admin/login with a "Session expired" flash

Scenario: OAuth login still triggers MFA when user.mfa_enabled is True
  Given user "alice" has mfa_enabled=True
  When  GET /oauth/callback/google completes successfully
  Then  a partial-auth session is created (no admin access)
  And   an OTP code is sent to alice's email
  And   the response redirects to /admin/mfa/challenge

Scenario: OAuth tokens are encrypted at rest
  Given an OAuthToken row exists for alice
  When  the access_token field is read directly from the database
  Then  the stored bytes are not equal to the plaintext access_token
  And   reading via OAuthToken.access_token returns the plaintext

Scenario: tenant_id_claim provisions tenant on first login
  Given OAuthProviderConfig has tenant_id_claim="hd"
  And   the IdP returns userinfo {"email": "alice@acme.com", "hd": "acme.com"}
  And   the host app maps domain "acme.com" → tenant_id 7
  When  GET /oauth/callback/google completes
  Then  the new User row has tenant_id = 7

Scenario: linking an OAuth identity from settings
  Given alice is fully authenticated and visits /admin/oauth/link/google
  When  alice completes the OAuth flow
  Then  an OAuthToken row is created for alice with provider="google"
  And   alice's User.email is unchanged
  And   the response redirects to /admin/oauth/settings with a success flash

Scenario: unlinking an OAuth identity from settings
  Given alice has an OAuthToken row for provider="google"
  And   alice has a usable password (i.e. is not OAuth-only)
  When  alice POSTs /admin/oauth/unlink/google
  Then  the OAuthToken row is deleted
  And   alice can still log in with password

Scenario: cannot unlink the only auth method
  Given alice has an OAuthToken for provider="google"
  And   alice's password_hash is None (provisioned via OAuth)
  When  alice POSTs /admin/oauth/unlink/google
  Then  the response is 400 Bad Request
  And   the body contains "Set a password before unlinking your only sign-in method"
```

## Design

### Architecture

```
                ┌──────────────────────────┐
                │     auth/oauth/          │   (new package)
                │  ─ backend.py            │   OAuthBackend (AuthBackend impl)
                │  ─ providers.py          │   OAuthProviderConfig + builders
                │  ─ tokens.py             │   FernetTokenCipher
                │  ─ refresh.py            │   OAuthRefreshMiddleware
                │  ─ exceptions.py         │   OAuthProviderError, AccountLinkRequiredError
                │  ─ views.py              │   /oauth/authorize, /oauth/callback, link, unlink
                └────────────┬─────────────┘
                             │ uses (Protocol)
                             ▼
                ┌────────────────────────┐
                │   core/auth.py         │  AuthBackend (existing)
                │                        │  + OAuthBackend conforms
                └────────────────────────┘
                             ▲
                             │ implements
                             │
        ┌────────────────────┴───────────────────────┐
        │   auth/views.py (mod) — login_view shows   │
        │   provider buttons; reuses existing MFA    │
        │   redirect flow on partial-auth sessions   │
        └────────────────────────────────────────────┘
                             ▲
                             │ persistence
                             │
        ┌────────────────────┴────────────────────┐
        │   auth/models.py (mod)                  │
        │   + OAuthToken (encrypted access/       │
        │      refresh tokens, expiry, scopes)    │
        │   + User.password_hash → Optional       │
        │   + User.oauth_only computed property   │
        └─────────────────────────────────────────┘
```

Module layout:

```
src/hyperadmin/auth/oauth/
├── __init__.py        — public exports
├── backend.py         — OAuthBackend (implements AuthBackend)
├── providers.py       — OAuthProviderConfig, google_provider(), github_provider()
├── tokens.py          — FernetTokenCipher, helpers
├── refresh.py         — OAuthRefreshMiddleware
├── exceptions.py      — OAuthProviderError, AccountLinkRequiredError, MFARequiredError
└── views.py           — authorize, callback, link, unlink, settings handlers

src/hyperadmin/auth/
├── models.py          — (mod) add OAuthToken; relax User.password_hash to Optional
├── views.py           — (mod) login page renders provider buttons
└── __init__.py        — (mod) re-export OAuthBackend, OAuthProviderConfig

src/hyperadmin/templates/auth/
├── login.html         — (mod) provider button rows
├── oauth_link_required.html  — (new) account-link interstitial
└── oauth_settings.html        — (new) per-user link/unlink view
```

Dependency direction:

- `auth/oauth/` → `auth/` and `core/` (one direction, no cycles).
- `auth/oauth/views.py` consumes the existing `core/auth.AuthBackend` Protocol and produces
  full-auth or partial-auth sessions through the same helpers `auth/views.py` already uses.

Library choice — `httpx-oauth` (`>=0.13`):

- Battle-tested in `fastapi-users`.
- Async-native (`httpx`).
- Built-in Google and GitHub provider classes; OIDC discovery for Google.
- PKCE supported.
- 23 KB of dependencies — small footprint.

### Data Model Changes

```python
# src/hyperadmin/auth/models.py

class OAuthToken(SQLModel, table=True):
    __tablename__ = "hyperadmin_oauth_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="hyperadmin_users.id", index=True)
    provider: str = Field(max_length=32, index=True)
    sub: str = Field(max_length=255, index=True)  # IdP-side stable user id
    access_token_encrypted: bytes
    refresh_token_encrypted: bytes | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("provider", "sub", name="uq_oauth_provider_sub"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    @property
    def access_token(self) -> str:
        return _cipher().decrypt(self.access_token_encrypted).decode()

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.access_token_encrypted = _cipher().encrypt(value.encode())

    # refresh_token property mirrors access_token, handling None
```

`User` model changes (additive, backward compatible):

```python
class User(SQLModel, table=True):
    ...
    password_hash: str | None = Field(default=None)  # was required; now optional for OAuth-only

    @property
    def oauth_only(self) -> bool:
        return self.password_hash is None
```

Existing rows already have `password_hash` set; the column type loosening is a no-op at the
SQL level (NULLability change is the only schema effect, and host apps own that migration).

### API / Protocol Changes

**`OAuthProviderConfig`** (frozen dataclass, no Pydantic — config is wired in code):

```python
@dataclass(frozen=True, slots=True)
class OAuthProviderConfig:
    name: str                       # "google" | "github" | custom
    client_id: str
    client_secret: str
    scopes: tuple[str, ...]
    authorize_url: str
    token_url: str
    userinfo_url: str
    sub_claim: str = "sub"          # GitHub uses "id"; Google uses "sub"
    email_claim: str = "email"
    tenant_id_claim: str | None = None
    button_label: str | None = None
    button_icon: str | None = None  # path under /static/
```

Helper builders:

```python
def google_provider(client_id: str, client_secret: str, *, hosted_domain: str | None = None,
                    tenant_id_claim: str | None = None) -> OAuthProviderConfig: ...
def github_provider(client_id: str, client_secret: str, *,
                    scopes: tuple[str, ...] = ("read:user", "user:email")) -> OAuthProviderConfig: ...
```

**`OAuthBackend`** implements `AuthBackend`:

```python
class OAuthBackend:
    def __init__(self, providers: dict[str, OAuthProviderConfig], session_factory): ...
    async def login(self, request, user) -> None: ...   # existing AuthBackend contract
    async def logout(self, request) -> None: ...
    async def authorize(self, request, provider: str) -> RedirectResponse: ...
    async def callback(self, request, provider: str) -> Response: ...
```

**Endpoints** (registered when `Admin(oauth_backend=OAuthBackend(...))`):

| Method | Path | Purpose |
|---|---|---|
| GET  | `/admin/oauth/authorize/{provider}` | Build authorize URL with PKCE + state, redirect |
| GET  | `/admin/oauth/callback/{provider}`  | Validate state, exchange code, provision/log in |
| GET  | `/admin/oauth/settings`             | Render link/unlink view (auth required) |
| GET  | `/admin/oauth/link/{provider}`      | Initiate link flow from settings (auth required) |
| POST | `/admin/oauth/unlink/{provider}`    | Delete OAuthToken row (auth required) |

**`Admin(...)`** gains:

```python
def __init__(
    self,
    ...,
    oauth_backend: OAuthBackend | None = None,
) -> None: ...
```

When provided, `__init__` mounts `OAuthRefreshMiddleware` and registers the routes above.

**Public exports** added to `hyperadmin.__init__`:

```python
from hyperadmin.auth.oauth import (
    OAuthBackend,
    OAuthProviderConfig,
    OAuthProviderError,
    AccountLinkRequiredError,
    google_provider,
    github_provider,
)
```

### Configuration Changes

| Variable | Default | Description |
|---|---|---|
| `HYPERADMIN_OAUTH_TOKEN_SECRET` | (none — required if OAuth used) | 32-byte url-safe base64 Fernet key |
| `HYPERADMIN_OAUTH_STATE_TTL_SECONDS` | `600` | Authorize-state expiry |
| `HYPERADMIN_OAUTH_REFRESH_LEEWAY_SECONDS` | `60` | Refresh tokens this many seconds before expiry |
| `HYPERADMIN_OAUTH_LOGIN_REDIRECT` | `"/admin/"` | Post-login destination |

Per-app code wiring:

```python
admin = Admin(
    app,
    oauth_backend=OAuthBackend(providers={
        "google": google_provider(env["GOOGLE_CLIENT_ID"], env["GOOGLE_CLIENT_SECRET"],
                                  hosted_domain="acme.com", tenant_id_claim="hd"),
        "github": github_provider(env["GH_CLIENT_ID"], env["GH_CLIENT_SECRET"]),
    }),
)
```

## Edge Cases & Error Handling

| Case | Handling |
|---|---|
| `HYPERADMIN_OAUTH_TOKEN_SECRET` missing while OAuth configured | Hard fail at `Admin.__init__` — refuse to start |
| Fernet key rotation | Two-key support: list-of-keys env var, decrypt with any, encrypt with first. Documented; v0.5.2+ feature |
| State nonce reused | Single-use — deleted from session on first callback hit |
| State nonce missing | 400 Bad Request — likely cookie cleared mid-flow |
| Provider returns no email (GitHub privacy) | Fall back to provider's `/user/emails` endpoint with `read:user`+`user:email` scopes; if still none, 400 with "Email required" |
| Provider userinfo schema drifts | `OAuthProviderConfig` exposes `sub_claim` / `email_claim` so the host can patch without code change |
| Same email, two different `sub` values across providers | Treated as account-link conflict — settings flow links explicitly |
| Email collision with local user (no OAuth row) | 409 with link-required interstitial; **never** auto-link |
| Email collision with another OAuth-provisioned user (different IdP `sub`) | 409 — user must log in with the other identity and link from settings |
| Token refresh failure (network) | Retry once with 1s backoff inside middleware; on second failure, leave token as-is, allow request to proceed (admin endpoints will 401 if access token is rejected) |
| Token refresh failure (`invalid_grant`) | Hard — clear session, redirect to login with flash |
| User-agent strips cookies between authorize and callback | State validation fails → 400; user clicks login again, new flow |
| MFA-enabled user completes OAuth | Partial-auth session, redirect to `/admin/mfa/challenge`. Existing OTP service handles the rest |
| Tenant claim present but no domain mapping | New user gets `tenant_id=None` (admin must assign). Logged at INFO |
| Tenant claim absent on returning user | Don't overwrite existing `tenant_id` — preserve admin assignment |
| OAuth-only user disables MFA | Allowed; OAuth login still requires the IdP's authentication |
| OAuth unlink would orphan the user | Reject with 400 ("Set a password before unlinking your only sign-in method") |
| Concurrent callback (two tabs) | Latest one wins; tokens upserted on `(provider, sub)` unique constraint |
| Provider request to `userinfo` returns 401 | Treat as expired access token; trigger refresh; on refresh failure, 502 to user |
| Webhook / API token use of OAuth tokens | Out of scope — OAuth tokens are session-coupled. Documented |

## Migration & Backward Compatibility

- **No breaking changes.**
- **DB migration owned by host app** (single table add: `hyperadmin_oauth_tokens`; one
  column nullability change on `hyperadmin_users.password_hash`). Documented in changelog.
- **`User.password_hash` → Optional** is read-compatible — existing values keep working.
- **Public API** is additive. `__init__.py` exports added; nothing renamed/removed.
- **Existing `AuthBackend` implementations** continue to work — `OAuthBackend` is a peer,
  not a replacement.
- **MFA + OAuth interaction** preserves the v0.5.1 partial-auth session shape.

## Open Questions

- [x] Library: `httpx-oauth` vs hand-rolled? → **`httpx-oauth`.** PKCE + token refresh +
      provider classes in 23 KB. Pinning `>=0.13,<1.0`.
- [x] Token storage: encrypt at rest or rely on DB-level encryption? → **Encrypt at rest.**
      Defense in depth; cheap; one Fernet roundtrip per request is negligible.
- [x] Auto-link by email or interstitial? → **Interstitial.** Auto-link is a known SSO
      vulnerability when IdP email isn't verified or attacker controls the email's MX.
- [x] OAuth-only users: allow no password? → **Yes**, gated on a unlink check that
      requires either a password or another linked OAuth identity.
- [x] Where do PKCE verifier and state nonce live? → **Session.** No new table.
      State carries TTL via session timestamp.
- [x] Token refresh: middleware vs background task? → **Middleware.** Background tasks
      add complexity (Redis, scheduler) and don't help if the user is offline anyway.
- [ ] Group/role provisioning from OAuth claims? → **Deferred.** v0.5.2 only provisions
      the User row. Group sync needs an SDD of its own (ties into v0.5.x permissions).
      Resolved on approval as out-of-scope.
- [ ] Rate-limiting on the callback endpoint? → **Yes**, per-IP rate limit on
      `/oauth/callback/{provider}`. Reuses the OTP rate limiter pattern. Final knob:
      `HYPERADMIN_OAUTH_CALLBACK_RATE_LIMIT=(20, 60)` (20 attempts / minute / IP).
      Resolved on approval.

## Decision Log

| Decision | Rationale | Alternatives considered |
|---|---|---|
| `httpx-oauth` library | Mature, async, supports PKCE + Google + GitHub out of the box; small footprint | `authlib` (heavier, more features we don't need); hand-rolled (PKCE + token refresh easy to misimplement) |
| PKCE on by default | Cheap; protects against `client_secret` exposure in misconfigured deployments | Skip PKCE for confidential clients — rejected, no downside to enabling |
| Encrypt tokens at rest with Fernet | Defense in depth; single dep (`cryptography`) already transitive | Plain text + DB encryption — relies on host config; AES-GCM custom impl — reinventing |
| Account-link interstitial on email collision | Auto-link is a known SSO takeover vector | Auto-link by verified email — fragile; some IdPs lie about verification |
| Refresh in middleware | Predictable; no background infra | Background task — adds Redis dep + scheduling; cron — too coarse |
| Tenant claim mapping is optional | Single-tenant apps must not be forced into a claim mapping | Mandatory tenant claim — couples OAuth to multi-tenancy |
| `OAuthProviderConfig` is a `dataclass`, not Pydantic | Wired in code, not env; immutable; no validation cost per request | Pydantic model — adds runtime cost without benefit |
| Two endpoints per provider (`authorize`, `callback`) | Maps directly to OAuth2 spec | Single endpoint — harder to reason about / log |
| Settings flow for link/unlink | Mirrors MFA settings UX from v0.5.1 | Inline on profile page — too crowded; magic link in email — out of scope |
| `User.password_hash` becomes Optional | Required to support OAuth-only users | Sentinel password ("oauth_only") — hostile to debugging |
| Exceptions: `OAuthProviderError`, `AccountLinkRequiredError`, `MFARequiredError` | Structured failure modes the views can render to specific templates | Generic `HTTPException` with codes — couples flow to status codes |
| Provider button rendering only for configured providers | Avoid 404 buttons | Always render — confusing UX |
