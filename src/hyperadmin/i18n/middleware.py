"""Locale negotiation middleware for HyperAdmin.

Resolves the active locale per request, in priority order:

1. ``hyperadmin_locale`` cookie (set by the locale switcher).
2. ``Accept-Language`` header (negotiated against ``supported_locales``).
3. ``settings.default_locale``.

The resolved code is stored on ``request.state.locale`` so view handlers and
the Jinja context processor can read it. When ``settings.locale_response_header``
is true (default), a matching ``Content-Language`` response header is set.

Mirrors the shape of :class:`hyperadmin.auth.middleware.AuthenticationMiddleware`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import babel
from starlette.middleware.base import BaseHTTPMiddleware

from hyperadmin.i18n.loader import (
    load_translations,
    reset_current_translations,
    set_current_translations,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request
    from starlette.responses import Response

    from hyperadmin.core.settings import HyperAdminSettings


COOKIE_NAME = "hyperadmin_locale"

#: Locale codes whose natural reading direction is right-to-left.
#:
#: Used by :func:`hyperadmin.core.app.Admin.mount` to expose ``rtl_locales``
#: as a Jinja2 global so ``_base.html`` can render ``<html dir="rtl">``.
#: Two of the 20 default seeded locales (``ar``, ``he``) are RTL; the other
#: two entries (``fa``, ``ur``) remain opt-in via ``HYPERADMIN_SUPPORTED_LOCALES``.
RTL_LOCALES: frozenset[str] = frozenset({"ar", "he", "fa", "ur"})


def _parse_accept_language(header: str) -> list[str]:
    """Return preferred locale codes ordered by quality, normalised to BCP47-with-underscore.

    ``en-US`` -> ``en_US``. Items with malformed q-values default to ``q=1.0``.
    Empty / whitespace-only fragments are skipped. Unparseable headers yield an
    empty list (the caller falls back to the default locale).
    """
    items: list[tuple[str, float]] = []
    for raw in header.split(","):
        part = raw.strip()
        if not part:
            continue
        if ";" in part:
            head, *params = part.split(";")
            quality = 1.0
            for param in params:
                key, _, value = param.strip().partition("=")
                if key == "q":
                    try:
                        quality = float(value)
                    except ValueError:
                        quality = 1.0
            code = head.strip()
        else:
            code = part
            quality = 1.0
        if not code:
            continue
        items.append((code.replace("-", "_"), quality))
    items.sort(key=lambda pair: -pair[1])
    return [code for code, _ in items]


def negotiate_locale(
    *,
    cookie_value: str | None,
    accept_language: str | None,
    supported: Sequence[str],
    default: str,
) -> str:
    """Resolve the request locale.

    Returns the first match in this order:

    1. ``cookie_value`` if it appears in ``supported``.
    2. The best Accept-Language match against ``supported`` (via
       :func:`babel.negotiate_locale`).
    3. ``default``.

    Unsupported cookie values are silently ignored (the cookie is treated as
    user input, not corrupted state). Malformed Accept-Language headers cannot
    crash the resolver -- any parsing error falls through to ``default``.
    """
    supported_list = list(supported)
    if cookie_value and cookie_value in supported_list:
        return cookie_value
    if accept_language:
        try:
            preferred = _parse_accept_language(accept_language)
            if preferred:
                negotiated = babel.negotiate_locale(preferred, supported_list, sep="_")
                if negotiated:
                    return negotiated
        except (ValueError, babel.UnknownLocaleError):
            pass
    return default


class LocaleMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that resolves the request locale and stores it on state.

    Args:
        app: The downstream ASGI app.
        settings: A ``HyperAdminSettings`` instance whose ``default_locale``,
            ``supported_locales``, and ``locale_response_header`` fields drive
            negotiation behaviour.
    """

    def __init__(self, app: Any, settings: HyperAdminSettings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        locale = negotiate_locale(
            cookie_value=request.cookies.get(COOKIE_NAME),
            accept_language=request.headers.get("accept-language"),
            supported=self.settings.supported_locales,
            default=self.settings.default_locale,
        )
        translations = load_translations(locale)
        request.state.locale = locale
        request.state.translations = translations
        token = set_current_translations(translations)
        try:
            response = await call_next(request)
        finally:
            reset_current_translations(token)
        if self.settings.locale_response_header:
            response.headers["Content-Language"] = locale
        return response
