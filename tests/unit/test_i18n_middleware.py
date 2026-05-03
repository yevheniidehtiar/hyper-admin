"""Unit tests for hyperadmin.i18n.middleware.LocaleMiddleware.

Covers the BDD scenarios from
.meta/epics/epic-i18n/stories/c1b-locale-middleware.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.middleware import LocaleMiddleware, negotiate_locale

if TYPE_CHECKING:
    from collections.abc import Iterator


# ---------------------------------------------------------------------------
# Pure resolver tests (no HTTP)
# ---------------------------------------------------------------------------


class TestNegotiateLocale:
    def test_no_cookie_no_accept_language_falls_back_to_default(self) -> None:
        assert (
            negotiate_locale(
                cookie_value=None,
                accept_language=None,
                supported=("en", "es"),
                default="en",
            )
            == "en"
        )

    def test_cookie_overrides_accept_language(self) -> None:
        assert (
            negotiate_locale(
                cookie_value="es",
                accept_language="fr-FR",
                supported=("en", "es", "fr"),
                default="en",
            )
            == "es"
        )

    def test_accept_language_used_when_no_cookie(self) -> None:
        assert (
            negotiate_locale(
                cookie_value=None,
                accept_language="de-DE,de;q=0.9,en;q=0.8",
                supported=("en", "fr", "de"),
                default="en",
            )
            == "de"
        )

    def test_unsupported_cookie_value_falls_back_to_default(self) -> None:
        # The cookie carries an unsupported locale and there is no
        # Accept-Language to fall back to, so we end up at the default.
        assert (
            negotiate_locale(
                cookie_value="zz",
                accept_language=None,
                supported=("en", "es"),
                default="en",
            )
            == "en"
        )

    def test_unsupported_cookie_falls_through_to_accept_language(self) -> None:
        assert (
            negotiate_locale(
                cookie_value="zz",
                accept_language="es-ES",
                supported=("en", "es"),
                default="en",
            )
            == "es"
        )

    def test_malformed_accept_language_falls_back_to_default(self) -> None:
        assert (
            negotiate_locale(
                cookie_value=None,
                accept_language="!@#$",
                supported=("en", "es"),
                default="en",
            )
            == "en"
        )

    @pytest.mark.parametrize(
        ("header", "supported", "expected"),
        [
            ("en-US,en;q=0.9", ("en", "es"), "en"),
            ("zh-CN", ("en", "zh_CN"), "zh_CN"),
            ("ja-JP,ja;q=0.8,en;q=0.5", ("en", "ja"), "ja"),
            ("uk-UA;q=0.6,en;q=0.4", ("en", "uk"), "uk"),
            ("fr,en;q=0.5", ("en", "es"), "en"),  # fr unsupported -> en wins
        ],
    )
    def test_accept_language_parametrized(
        self, header: str, supported: tuple[str, ...], expected: str
    ) -> None:
        assert (
            negotiate_locale(
                cookie_value=None,
                accept_language=header,
                supported=supported,
                default="en",
            )
            == expected
        )


# ---------------------------------------------------------------------------
# HTTP-level middleware tests
# ---------------------------------------------------------------------------


def _make_client(settings: HyperAdminSettings) -> TestClient:
    """Build a tiny FastAPI app with LocaleMiddleware mounted."""
    app = FastAPI()
    app.add_middleware(LocaleMiddleware, settings=settings)

    @app.get("/")
    async def root(request: Request) -> JSONResponse:
        return JSONResponse({"locale": request.state.locale})

    return TestClient(app)


@pytest.fixture
def en_settings() -> Iterator[HyperAdminSettings]:
    return HyperAdminSettings(
        default_locale="en",
        supported_locales=["en", "es", "fr", "de", "zh_CN", "ja", "uk"],
    )


class TestLocaleMiddlewareDispatch:
    def test_default_locale_when_no_signals(self, en_settings: HyperAdminSettings) -> None:
        # Given Admin app with default settings
        client = _make_client(en_settings)
        # When request has no cookie and no Accept-Language
        response = client.get("/")
        # Then request.state.locale == "en"
        assert response.json() == {"locale": "en"}

    def test_cookie_overrides_accept_language(self, en_settings: HyperAdminSettings) -> None:
        # Given supported_locales=["en","es","fr"]
        client = _make_client(en_settings)
        # When cookie hyperadmin_locale=es, Accept-Language=fr-FR
        response = client.get(
            "/",
            headers={"Accept-Language": "fr-FR"},
            cookies={"hyperadmin_locale": "es"},
        )
        # Then request.state.locale == "es"
        assert response.json() == {"locale": "es"}

    def test_accept_language_negotiated_when_no_cookie(
        self, en_settings: HyperAdminSettings
    ) -> None:
        client = _make_client(en_settings)
        response = client.get("/", headers={"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        assert response.json() == {"locale": "de"}

    def test_unsupported_cookie_value_silently_ignored(
        self, en_settings: HyperAdminSettings
    ) -> None:
        client = _make_client(en_settings)
        response = client.get("/", cookies={"hyperadmin_locale": "zz"})
        assert response.json() == {"locale": "en"}
        # Cookie not cleared (no Set-Cookie header for hyperadmin_locale)
        assert "set-cookie" not in {k.lower() for k in response.headers}

    def test_malformed_accept_language_does_not_crash(
        self, en_settings: HyperAdminSettings
    ) -> None:
        client = _make_client(en_settings)
        response = client.get("/", headers={"Accept-Language": "!@#$"})
        assert response.status_code == 200
        assert response.json() == {"locale": "en"}


class TestContentLanguageHeader:
    def test_set_by_default(self, en_settings: HyperAdminSettings) -> None:
        client = _make_client(en_settings)
        response = client.get("/", headers={"Accept-Language": "es-ES"})
        assert response.headers.get("content-language") == "es"

    def test_suppressed_when_setting_disabled(self) -> None:
        settings = HyperAdminSettings(
            default_locale="en",
            supported_locales=["en", "es"],
            locale_response_header=False,
        )
        client = _make_client(settings)
        response = client.get("/", headers={"Accept-Language": "es-ES"})
        assert "content-language" not in {k.lower() for k in response.headers}

    def test_reflects_resolved_locale(self, en_settings: HyperAdminSettings) -> None:
        client = _make_client(en_settings)
        response = client.get("/", cookies={"hyperadmin_locale": "uk"})
        assert response.headers.get("content-language") == "uk"
