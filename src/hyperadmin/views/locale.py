"""Locale switcher endpoint for HyperAdmin.

Provides a ``POST /admin/locale`` handler that sets the ``hyperadmin_locale``
cookie and redirects the user back to the page they came from.

The locale is validated against ``settings.supported_locales``.  An
unsupported value results in a plain 400 response — no cookie is written.

Cookie attributes (C2-D spec, BYOA SDD C.1/C.4):

- ``Path=<admin path>`` — the per-request admin path, so the cookie is sent
  back under any mount prefix and host ``root_path`` (``/backoffice``,
  ``/api/admin``)
- ``HttpOnly``      — not accessible via JS
- ``SameSite=Lax``  — CSRF mitigation without breaking same-site navigations
- ``Secure``        — per ``settings.cookie_secure``
- ``Max-Age=31536000`` — one year

The redirect goes back to the ``Referer`` only when it is a same-origin URL
under the admin path; anything else (another host, a host page, a
scheme-relative or backslash trick) falls back to the dashboard, so the
switcher cannot be used as an open redirect.

No GET handler is registered for this path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse, RedirectResponse, Response

from hyperadmin.core.settings import resolve_cookie_secure
from hyperadmin.views.urls import request_admin_path

if TYPE_CHECKING:
    from starlette.requests import Request

    from hyperadmin.core.settings import HyperAdminSettings

_COOKIE_NAME = "hyperadmin_locale"
_COOKIE_MAX_AGE = 31_536_000  # 365 days in seconds


def _safe_referer_target(request: Request, admin_path: str) -> str | None:
    """Return the ``Referer`` as a relative admin URL, or ``None`` when unsafe.

    The ``Referer`` is used only when it is same-origin (or relative) and its
    path is the admin path or lies below it on a segment boundary.
    """
    referer = request.headers.get("referer", "").strip()
    if not referer or "\\" in referer:
        return None
    parts = urlsplit(referer)
    if parts.netloc:
        if parts.scheme not in ("http", "https") or parts.netloc != request.url.netloc:
            return None
    elif parts.scheme:
        return None
    path = parts.path
    if path.startswith("//"):
        return None
    if not (path == admin_path or path.startswith(f"{admin_path}/")):
        return None
    return f"{path}?{parts.query}" if parts.query else path


async def set_locale_view(
    request: Request,
    settings: HyperAdminSettings,
    admin_prefix: str,
) -> Response:
    """Handle ``POST /admin/locale``.

    Reads the ``locale`` field from the form body, validates it against
    ``settings.supported_locales``, writes the cookie, and redirects to the
    ``Referer`` header when it is a same-origin admin URL (falling back to
    ``<admin path>/``).

    Args:
        request: The current Starlette/FastAPI request.
        settings: The ``HyperAdminSettings`` instance attached to the admin.
        admin_prefix: The path prefix the admin is mounted on (e.g. ``/admin``),
            used when the request carries no per-request admin path.

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

    admin_path = request_admin_path(request, admin_prefix)
    redirect_url = _safe_referer_target(request, admin_path) or f"{admin_path}/"

    response: Response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=locale,
        path=admin_path or "/",
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=resolve_cookie_secure(settings.cookie_secure, request.url.scheme),
    )
    return response
