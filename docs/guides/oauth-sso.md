# OAuth Sign-In (Google, GitHub)

HyperAdmin's built-in authentication can sign users in through an OAuth2/OIDC identity
provider next to the username and password form. Google and GitHub ship ready to use;
any other OIDC provider needs only a configuration object.

OAuth is opt-in. Without `Admin(oauth_backend=...)` nothing changes: no button, no route,
no extra import and no query against the token table.

!!! note "Bring-your-own-auth hosts"
    OAuth sign-in belongs to the built-in auth (`auth_backend=`). With
    [`Admin(auth=ExternalAuth(...))`](external-auth.md) your application owns sign-in,
    including any OAuth flow, so the two options cannot be combined.

## Install

```bash
pip install 'hyper-admin[oauth]'
```

The extra adds `httpx-oauth` and `cryptography`.

## Configure

1. Create an OAuth client at the provider. Its redirect URI is
   `https://<your-host>/admin/oauth/callback/<provider>`, for example
   `https://admin.example.com/admin/oauth/callback/google`.
2. Generate a key for encrypting stored tokens and set it as
   `HYPERADMIN_OAUTH_TOKEN_SECRET`:

    ```bash
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```

3. Pass an `OAuthBackend` to `Admin`:

    ```python
    import os

    from hyperadmin import Admin, OAuthBackend, github_provider, google_provider
    from hyperadmin.auth.session import SessionAuthBackend

    admin = Admin(
        app,
        engine=engine,
        auth_backend=SessionAuthBackend(engine=engine),
        oauth_backend=OAuthBackend(
            providers={
                "google": google_provider(
                    os.environ["GOOGLE_CLIENT_ID"],
                    os.environ["GOOGLE_CLIENT_SECRET"],
                    hosted_domain="example.com",
                ),
                "github": github_provider(
                    os.environ["GITHUB_CLIENT_ID"],
                    os.environ["GITHUB_CLIENT_SECRET"],
                    allow_signup=False,
                ),
            }
        ),
    )
    admin.mount("/admin")
    ```

4. Create the `hyperadmin_oauth_tokens` table: run `hyperadmin init-db`, or add it with
   your migrations (`hyperadmin.auth.metadata()` includes it).

The login page now shows a "Sign in with ..." button per provider. `Admin` refuses to
start when the key is missing.

## Who can sign in

| Situation | Result |
|---|---|
| The identity was used before | The same user is signed in; stored tokens are replaced. |
| New identity, no user has its email | A user is created with no usable password and no permissions. |
| New identity, a user already has its email | `409`: accounts are never linked by email. The user signs in with the password and links the provider under `/admin/oauth/settings`. |
| New identity and `allow_signup=False` | `403`: only users who linked the provider can use it. |
| The user is inactive | `403`. |
| The user has MFA enabled | The OAuth sign-in continues at the MFA challenge. |

A new user holds no permission until an administrator grants some. For a provider anyone
can register at (GitHub, a public Google account), set `allow_signup=False`, or restrict
Google to a Workspace domain with `hosted_domain=`; a sign-in from another domain is
refused.

Users manage their linked providers at `/admin/oauth/settings`. A provider cannot be
unlinked while it is the user's only way to sign in.

## Settings

| Setting | Environment variable | Default | Meaning |
|---|---|---|---|
| `oauth_token_secret` | `HYPERADMIN_OAUTH_TOKEN_SECRET` | none (required with OAuth) | Fernet key for stored tokens. Several keys separated by commas rotate it: the first encrypts, all decrypt. |
| `oauth_state_ttl_seconds` | `HYPERADMIN_OAUTH_STATE_TTL_SECONDS` | `600` | Time a sign-in may take between the redirect and the callback. |
| `oauth_refresh_leeway_seconds` | `HYPERADMIN_OAUTH_REFRESH_LEEWAY_SECONDS` | `60` | An access token is refreshed when it expires within this time. |
| `oauth_login_redirect` | `HYPERADMIN_OAUTH_LOGIN_REDIRECT` | admin index | Where a completed sign-in lands. |
| `oauth_callback_rate_limit` | `HYPERADMIN_OAUTH_CALLBACK_RATE_LIMIT` | `[20, 60]` | Callback requests per client and window in seconds (counted per process). |

## Another OIDC provider

```python
from hyperadmin import OAuthProviderConfig

okta = OAuthProviderConfig(
    name="okta",
    client_id=os.environ["OKTA_CLIENT_ID"],
    client_secret=os.environ["OKTA_CLIENT_SECRET"],
    scopes=("openid", "email", "profile", "offline_access"),
    authorize_url="https://example.okta.com/oauth2/v1/authorize",
    token_url="https://example.okta.com/oauth2/v1/token",
    userinfo_url="https://example.okta.com/oauth2/v1/userinfo",
    button_label="Okta",
)
```

`sub_claim` and `email_claim` name the userinfo keys when a provider deviates from OIDC.
Behind a proxy that hides the public host, set `redirect_uri=` to the registered URL.

## How it works

- Every sign-in uses a single-use `state` and PKCE (`S256`), both kept in the signed admin
  session cookie.
- Access and refresh tokens are stored encrypted in `hyperadmin_oauth_tokens`.
- A session started by OAuth carries a marker with the token's expiry. A middleware
  refreshes the token shortly before it expires. If the provider rejects the refresh token
  (access was revoked), the session ends and the login page says so. If the provider is
  unreachable, the request proceeds and the refresh is tried again later. Password
  sessions carry no marker and are not touched.
- HyperAdmin uses the tokens only to keep the sign-in valid; it calls no other provider API.

## Limits

- `tenant_id_claim` and `OAuthBackend(tenant_resolver=...)` are accepted, but the built-in
  `User` has no tenant column yet, so the resolved tenant is only logged.
- Groups and permissions are not provisioned from provider claims.
- No provider-initiated logout and no SAML.
