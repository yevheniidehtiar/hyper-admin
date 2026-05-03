"""Locale switcher endpoint for HyperAdmin.

Provides a ``POST /admin/locale`` handler that sets the ``hyperadmin_locale``
cookie and redirects the user back to the page they came from.

The locale is validated against ``settings.supported_locales``.  An
unsupported value results in a plain 400 response — no cookie is written.

Cookie attributes (mandated by the C2-D spec):

- ``Path=/admin``   — scoped to the admin interface only
- ``HttpOnly``      — not accessible via JS
- ``SameSite=Lax``  — CSRF mitigation without breaking same-site navigations
- ``Max-Age=31536000`` — one year

No GET handler is registered for this path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import PlainTextResponse, RedirectResponse, Response

if TYPE_CHECKING:
    from starlette.requests import Request

    from hyperadmin.core.settings import HyperAdminSettings

_COOKIE_NAME = "hyperadmin_locale"
_COOKIE_MAX_AGE = 31_536_000  # 365 days in seconds
_COOKIE_PATH = "/admin"


async def set_locale_view(
    request: Request,
    settings: HyperAdminSettings,
    admin_prefix: str,
) -> Response:
    """Handle ``POST /admin/locale``.

    Reads the ``locale`` field from the form body, validates it against
    ``settings.supported_locales``, writes the cookie, and redirects to the
    ``Referer`` header (falling back to ``<admin_prefix>/``).

    Args:
        request: The current Starlette/FastAPI request.
        settings: The ``HyperAdminSettings`` instance attached to the admin.
        admin_prefix: The path prefix the admin is mounted on (e.g. ``/admin``).

    Returns:
        A 302 redirect on success or a 400 plain-text response when the
        requested locale is not in ``settings.supported_locales``.
    """
    form = await request.form()
    locale = str(form.get("locale", "")).strip()

    if locale not in settings.supported_locales:
        return PlainTextResponse(
            f"Unsupported locale: {locale!r}",
            status_code=400,
        )

    referer = request.headers.get("referer", "").strip()
    redirect_url = referer or f"{admin_prefix}/"

    response: Response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=locale,
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response
