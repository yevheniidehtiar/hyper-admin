"""Unit tests for the locale switcher endpoint (C2-D).

Covers the BDD scenarios from
.meta/epics/epic-i18n/stories/c2d-locale-switcher.md.

Scenario: switcher sets cookie and redirects
  Given supported_locales=["en","es"]
  When  POST /admin/locale with locale=es, Referer=/admin/users/
  Then  response is 302 to /admin/users/
  And   Set-Cookie: hyperadmin_locale=es; Path=/admin; HttpOnly; SameSite=Lax

Scenario: switcher redirects to /admin/ when no Referer
  When  POST /admin/locale with locale=es, no Referer header
  Then  redirect is 302 to /admin/

Scenario: unsupported locale returns 400
  Given supported_locales=["en","es"]
  When  POST /admin/locale with locale=zz
  Then  response is 400
  And   no Set-Cookie header

Scenario: subsequent request uses switched locale
  Given cookie hyperadmin_locale=es set by switcher
  When  GET /admin/
  Then  request.state.locale == "es"
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.middleware import LocaleMiddleware
from hyperadmin.views.locale import set_locale_view

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUPPORTED = [
    "en",
    "es",
    "fr",
    "de",
    "zh_CN",
    "ja",
    "uk",
    "ar",
    "he",
    "hi",
    "pt_BR",
    "ru",
    "ko",
    "it",
    "tr",
    "pl",
    "nl",
    "vi",
    "id",
    "th",
]


def _make_app(supported_locales: list[str] | None = None) -> tuple[FastAPI, HyperAdminSettings]:
    """Build a minimal FastAPI app wired with LocaleMiddleware and locale route."""
    locales = supported_locales if supported_locales is not None else _SUPPORTED
    settings = HyperAdminSettings(
        default_locale="en",
        supported_locales=locales,
    )

    app = FastAPI()
    # Add LocaleMiddleware so the "subsequent request" scenario can verify
    # that the cookie is read back correctly.
    app.add_middleware(LocaleMiddleware, settings=settings)

    admin_prefix = "/admin"

    @app.post("/admin/locale")
    async def locale_endpoint(request: Request) -> JSONResponse:
        return await set_locale_view(request, settings, admin_prefix)  # type: ignore[return-value]

    @app.get("/admin/")
    async def dashboard(request: Request) -> JSONResponse:
        return JSONResponse({"locale": request.state.locale})

    return app, settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLocaleSwitcherSetsCooke:
    """Scenario: switcher sets cookie and redirects to Referer."""

    def test_sets_cookie_and_redirects_to_referer(self) -> None:
        # Given supported_locales=["en","es","fr"]
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        # When POST /admin/locale with locale=es, Referer=/admin/users/
        response = client.post(
            "/admin/locale",
            data={"locale": "es"},
            headers={"Referer": "/admin/users/"},
        )

        # Then response is 302 to /admin/users/
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/users/"

        # And Set-Cookie: hyperadmin_locale=es; Path=/admin; HttpOnly; SameSite=Lax
        set_cookie = response.headers.get("set-cookie", "")
        set_cookie_lower = set_cookie.lower()
        assert "hyperadmin_locale=es" in set_cookie
        assert "path=/admin" in set_cookie_lower
        assert "httponly" in set_cookie_lower
        assert "samesite=lax" in set_cookie_lower


class TestLocaleSwitcherFallbackRedirect:
    """Scenario: switcher redirects to /admin/ when no Referer."""

    def test_redirects_to_admin_root_when_no_referer(self) -> None:
        # Given supported_locales=["en","es","fr"]
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        # When POST /admin/locale with locale=es, no Referer header
        response = client.post("/admin/locale", data={"locale": "es"})

        # Then redirect is 302 to /admin/
        assert response.status_code == 302
        assert response.headers["location"] == "/admin/"


class TestLocaleSwitcherUnsupportedLocale:
    """Scenario: unsupported locale returns 400."""

    def test_unsupported_locale_returns_400(self) -> None:
        # Given supported_locales=["en","es","fr"]
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        # When POST /admin/locale with locale=zz
        response = client.post("/admin/locale", data={"locale": "zz"})

        # Then response is 400
        assert response.status_code == 400

        # And no Set-Cookie header
        assert "set-cookie" not in {k.lower() for k in response.headers}

    def test_empty_locale_returns_400(self) -> None:
        """Edge case: empty locale string is not in supported list."""
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        response = client.post("/admin/locale", data={"locale": ""})

        assert response.status_code == 400
        assert "set-cookie" not in {k.lower() for k in response.headers}


class TestSubsequentRequestUsesLocale:
    """Scenario: subsequent request uses switched locale."""

    def test_cookie_is_read_by_locale_middleware(self) -> None:
        # Given cookie hyperadmin_locale=es set by switcher
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=True)

        # When GET /admin/ with cookie present
        response = client.get("/admin/", cookies={"hyperadmin_locale": "es"})

        # Then request.state.locale == "es"
        assert response.status_code == 200
        assert response.json() == {"locale": "es"}

    def test_cookie_from_switcher_is_read_by_middleware_end_to_end(self) -> None:
        """End-to-end: POST the switcher, then GET with the cookie; verify locale."""
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        # When POST /admin/locale — verify cookie is in the 302 response
        post_response = client.post(
            "/admin/locale",
            data={"locale": "fr"},
            headers={"Referer": "/admin/"},
        )
        assert post_response.status_code == 302
        set_cookie = post_response.headers.get("set-cookie", "")
        assert "hyperadmin_locale=fr" in set_cookie

        # When subsequent GET with the cookie that was just set
        get_response = client.get("/admin/", cookies={"hyperadmin_locale": "fr"})

        # Then request.state.locale == "fr"
        assert get_response.status_code == 200
        assert get_response.json() == {"locale": "fr"}


class TestCookieAttributes:
    """Verify all required cookie security attributes are present."""

    def test_cookie_has_max_age(self) -> None:
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        response = client.post(
            "/admin/locale",
            data={"locale": "es"},
        )

        set_cookie = response.headers.get("set-cookie", "")
        # Max-Age should be set (31536000 = 1 year)
        assert "Max-Age=31536000" in set_cookie

    def test_cookie_path_is_admin(self) -> None:
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        response = client.post(
            "/admin/locale",
            data={"locale": "es"},
        )

        set_cookie = response.headers.get("set-cookie", "")
        assert "Path=/admin" in set_cookie

    @pytest.mark.parametrize(
        "locale",
        [
            "en",
            "es",
            "fr",
            "de",
            "zh_CN",
            "ja",
            "uk",
            "ar",
            "he",
            "hi",
            "pt_BR",
            "ru",
            "ko",
            "it",
            "tr",
            "pl",
            "nl",
            "vi",
            "id",
            "th",
        ],
    )
    def test_all_supported_locales_set_cookie(self, locale: str) -> None:
        app, _ = _make_app()
        client = TestClient(app, follow_redirects=False)

        response = client.post("/admin/locale", data={"locale": locale})

        assert response.status_code == 302
        assert f"hyperadmin_locale={locale}" in response.headers.get("set-cookie", "")
