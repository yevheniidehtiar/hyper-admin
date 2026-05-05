"""Unit tests for C3-B — <html dir> driven by locale + RTL_LOCALES constant.

BDD scenarios covered
---------------------

Scenario: LTR locale sets dir="ltr"
  Given request.state.locale == "en"
  When  _base.html renders
  Then  <html dir="ltr" lang="en">

Scenario: RTL locale sets dir="rtl"
  Given supported_locales includes "ar" and request locale is "ar"
  When  _base.html renders
  Then  <html dir="rtl" lang="ar">

Scenario: RTL_LOCALES constant is correct
  Then  "ar", "he", "fa", "ur" are in RTL_LOCALES
  And   "en", "es", "fr", "de", "zh_CN", "ja", "uk" are NOT in RTL_LOCALES
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.testclient import TestClient

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.middleware import RTL_LOCALES, LocaleMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HYPERADMIN_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "src",
    "hyperadmin",
)
_TEMPLATE_DIR = os.path.join(_HYPERADMIN_SRC, "templates")
_STATIC_DIR = os.path.join(_HYPERADMIN_SRC, "static")


def _make_template_client(
    supported_locales: list[str],
    default_locale: str = "en",
) -> TestClient:
    """Build a minimal app with LocaleMiddleware that renders _base.html.

    The Jinja environment is wired exactly as Admin.mount() does it:
    - install_jinja_i18n for the gettext callables
    - rtl_locales global pointing to RTL_LOCALES
    - theme, site_title, site_header, admin_prefix, auth_enabled, supported_locales globals
    """
    from hyperadmin.i18n.loader import install_jinja_i18n

    settings = HyperAdminSettings(
        default_locale=default_locale,
        supported_locales=supported_locales,
        create_tables=False,
    )

    templates = Jinja2Templates(directory=_TEMPLATE_DIR)
    install_jinja_i18n(templates.env)
    templates.env.globals["rtl_locales"] = RTL_LOCALES
    templates.env.globals["theme"] = "auto"
    templates.env.globals["site_title"] = "HyperAdmin"
    templates.env.globals["site_header"] = "HyperAdmin"
    templates.env.globals["admin_prefix"] = "/admin"
    templates.env.globals["auth_enabled"] = False
    templates.env.globals["supported_locales"] = supported_locales

    app = FastAPI()
    # Mount static files so url_for('static', path=...) resolves in _base.html
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
    app.add_middleware(LocaleMiddleware, settings=settings)

    @app.get("/")
    async def root(request: Request) -> HTMLResponse:
        response = templates.TemplateResponse(request, "_base.html", {})
        return response  # type: ignore[return-value]

    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# RTL_LOCALES constant
# ---------------------------------------------------------------------------


class TestRTLLocalesConstant:
    """Scenario: RTL_LOCALES constant is correct."""

    def test_rtl_locales_is_a_frozenset(self) -> None:
        assert isinstance(RTL_LOCALES, frozenset)

    def test_rtl_codes_are_in_rtl_locales(self) -> None:
        # Then "ar", "he", "fa", "ur" are in RTL_LOCALES
        for code in ("ar", "he", "fa", "ur"):
            assert code in RTL_LOCALES, f"Expected {code!r} in RTL_LOCALES"

    def test_ltr_locales_are_not_in_rtl_locales(self) -> None:
        # And every LTR code in the v0.5.2 top-20 default is NOT in RTL_LOCALES.
        ltr_codes = (
            "en",
            "es",
            "fr",
            "de",
            "zh_CN",
            "ja",
            "uk",
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
        )
        for code in ltr_codes:
            assert code not in RTL_LOCALES, f"Expected {code!r} NOT in RTL_LOCALES"


# ---------------------------------------------------------------------------
# Template rendering — lang and dir attributes
# ---------------------------------------------------------------------------


class TestHtmlDirLtr:
    """Scenario: LTR locale sets dir="ltr"."""

    def test_html_has_lang_en_and_dir_ltr(self) -> None:
        # Given request.state.locale == "en" (no cookie, no Accept-Language)
        client = _make_template_client(supported_locales=["en", "es"])

        # When _base.html renders
        response = client.get("/")

        # Then <html dir="ltr" lang="en">
        assert response.status_code == 200
        body = response.text
        assert 'lang="en"' in body
        assert 'dir="ltr"' in body

    def test_html_has_lang_es_and_dir_ltr_for_spanish_cookie(self) -> None:
        # Given request locale resolved to "es" via cookie
        client = _make_template_client(supported_locales=["en", "es"])
        client.cookies.set("hyperadmin_locale", "es")

        # When _base.html renders with cookie hyperadmin_locale=es
        response = client.get("/")

        # Then <html dir="ltr" lang="es">
        assert response.status_code == 200
        body = response.text
        assert 'lang="es"' in body
        assert 'dir="ltr"' in body
        assert 'dir="rtl"' not in body


class TestHtmlDirRtl:
    """Scenario: RTL locale sets dir="rtl"."""

    def test_html_has_lang_ar_and_dir_rtl_for_arabic_cookie(self) -> None:
        # Given supported_locales includes "ar" and cookie sets locale to "ar"
        client = _make_template_client(supported_locales=["en", "ar"])
        client.cookies.set("hyperadmin_locale", "ar")

        # When _base.html renders with cookie hyperadmin_locale=ar
        response = client.get("/")

        # Then <html dir="rtl" lang="ar">
        assert response.status_code == 200
        body = response.text
        assert 'lang="ar"' in body
        assert 'dir="rtl"' in body

    @pytest.mark.parametrize("rtl_code", ["ar", "he", "fa", "ur"])
    def test_all_rtl_codes_produce_dir_rtl(self, rtl_code: str) -> None:
        # Given supported_locales includes the RTL locale
        client = _make_template_client(supported_locales=["en", rtl_code])
        client.cookies.set("hyperadmin_locale", rtl_code)

        # When _base.html renders with the RTL locale cookie
        response = client.get("/")

        # Then dir="rtl" and lang=<rtl_code>
        assert response.status_code == 200
        body = response.text
        assert f'lang="{rtl_code}"' in body
        assert 'dir="rtl"' in body

    def test_ltr_locale_does_not_produce_rtl_when_rtl_in_supported(self) -> None:
        # Given both "en" and "ar" are supported, but locale resolves to "en"
        client = _make_template_client(supported_locales=["en", "ar"])

        # When _base.html renders with no cookie (defaults to "en")
        response = client.get("/")

        # Then dir="ltr" — RTL_LOCALES must not leak into LTR sessions
        assert response.status_code == 200
        body = response.text
        assert 'dir="ltr"' in body
        assert 'dir="rtl"' not in body


# ---------------------------------------------------------------------------
# RTL_LOCALES re-export from hyperadmin.i18n
# ---------------------------------------------------------------------------


class TestRTLLocalesReExport:
    """Verify RTL_LOCALES is accessible from the package-level __init__."""

    def test_rtl_locales_importable_from_package(self) -> None:
        from hyperadmin.i18n import RTL_LOCALES as pkg_rtl_locales

        assert pkg_rtl_locales is RTL_LOCALES


# ---------------------------------------------------------------------------
# Admin.mount() wires rtl_locales as a Jinja global
# ---------------------------------------------------------------------------


class TestAdminMountRTLGlobal:
    """Verify Admin.mount() exposes rtl_locales in the Jinja environment."""

    def test_rtl_locales_set_as_jinja_global(self) -> None:
        from hyperadmin.core.app import Admin

        mock_app = MagicMock(spec=FastAPI)
        settings = HyperAdminSettings(create_tables=False)
        admin = Admin(app=mock_app, settings=settings)
        admin.mount("/admin")

        assert "rtl_locales" in admin.templates.env.globals
        assert admin.templates.env.globals["rtl_locales"] is RTL_LOCALES
