---
type: story
id: I18nMain_C1B
title: "feat(core): LocaleMiddleware (cookie > Accept-Language > default)"
status: todo
priority: high
assignee: null
labels:
  - backend
  - i18n
  - size:M
  - cycle:1
estimate: null
epic_ref:
  id: I18nMain_01
github: null
created_at: 2026-05-03T00:00:00Z
updated_at: 2026-05-03T00:00:00Z
---

## Summary

Introduce the `hyperadmin.i18n` package and a `LocaleMiddleware` that resolves the
request locale from `cookie > Accept-Language > settings.default_locale` and stores
it on `request.state.locale`. Mounted by `Admin.__init__`.

Mirrors `src/hyperadmin/auth/middleware.py:AuthenticationMiddleware` -- same
ASGI-middleware shape and `request.state.*` convention.

Spec: `docs/specs/i18n.md`

## Scenarios

**Scenario: default locale falls back to English**
  Given an Admin app with default settings
  When  a request arrives with no cookie and no Accept-Language
  Then  request.state.locale == "en"

**Scenario: cookie overrides Accept-Language**
  Given an Admin app with supported_locales=["en","es","fr"]
  When  a request arrives with cookie hyperadmin_locale=es and Accept-Language=fr-FR
  Then  request.state.locale == "es"

**Scenario: Accept-Language is parsed when no cookie is present**
  Given an Admin app with supported_locales=["en","fr","de"]
  When  a request arrives with Accept-Language="de-DE,de;q=0.9,en;q=0.8"
  Then  request.state.locale == "de"

**Scenario: unsupported cookie value is ignored**
  Given an Admin app with supported_locales=["en","es"]
  When  a request arrives with cookie hyperadmin_locale=zz
  Then  request.state.locale falls back to settings.default_locale
  And   the cookie is NOT cleared

**Scenario: malformed Accept-Language does not crash**
  Given an Admin app
  When  a request arrives with Accept-Language="!@#$"
  Then  request.state.locale falls back to settings.default_locale
  And   no exception escapes the middleware

**Scenario: Content-Language response header is set**
  Given an Admin app with default settings
  When  any admin response is sent
  Then  the response has header Content-Language matching request.state.locale
  And   setting HYPERADMIN_LOCALE_RESPONSE_HEADER=false suppresses it

## Acceptance criteria

- [ ] New package `src/hyperadmin/i18n/` with `__init__.py` exporting `LocaleMiddleware`
- [ ] `src/hyperadmin/i18n/middleware.py` implements ASGI middleware that sets `request.state.locale`
- [ ] Resolution order: cookie `hyperadmin_locale` > `Accept-Language` (via `babel.Locale.parse`) > `settings.default_locale`
- [ ] Unsupported values silently fall through (no exceptions, cookie not cleared)
- [ ] `Content-Language` response header set unless disabled via env
- [ ] `Admin.__init__` wires the middleware into the ASGI stack
- [ ] All scenarios above covered by unit tests in C3-D (this story leaves test scaffolding only)

## Files to modify

- `src/hyperadmin/i18n/__init__.py` (new) -- public exports
- `src/hyperadmin/i18n/middleware.py` (new) -- `LocaleMiddleware`
- `src/hyperadmin/core/app.py` -- mount the middleware in `Admin.__init__`
- `src/hyperadmin/core/settings.py` -- add `locale_response_header: bool = True`

## Implementation notes

- Use Starlette's `BaseHTTPMiddleware` or a pure-ASGI middleware following the
  shape of `auth/middleware.py:AuthenticationMiddleware`.
- For Accept-Language parsing, prefer `babel.negotiate_locale(preferred, available)`
  over manual q-value parsing -- handles weighting and fallbacks.
- Cookie name: `hyperadmin_locale`. Read-only here; the switcher (C2-D) writes it.
- Mount **after** the auth middleware so authenticated requests can still resolve
  locale. Order in `Admin.__init__`: SessionMiddleware -> AuthenticationMiddleware
  -> LocaleMiddleware -> CSRF -> route handlers.

## Demo checkpoint

```python
from starlette.testclient import TestClient
from hyperadmin import Admin
from sqlmodel import SQLModel, create_engine

admin = Admin(create_engine("sqlite:///:memory:"))
client = TestClient(admin.app)
r = client.get("/admin/", headers={"Accept-Language": "es-ES"})
assert r.headers.get("Content-Language") == "es"
```

## Agent

- **Size:** M
- **Tier:** Sonnet
- **blocked_by:** C1-A (needs `default_locale` / `supported_locales` settings)
