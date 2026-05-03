"""Login, logout and MFA view handlers for HyperAdmin.

The MFA endpoints (``/mfa/challenge``, ``/mfa/verify``, ``/mfa/resend``)
were added in v0.5.1 (C2-D, #486). They consume the partial-auth marker
written under ``PARTIAL_AUTH_SESSION_KEY`` by ``login_view``. The actual
wiring of ``login_view`` to populate that marker, plus the middleware
gate that redirects partial-auth users to the challenge, lands in C3-A
— this module only owns the consumer side.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from starlette.responses import RedirectResponse

from hyperadmin.auth.models import User
from hyperadmin.auth.otp import (
    OTP_SESSION_KEY,
    PARTIAL_AUTH_SESSION_KEY,
    RateLimitError,
)
from hyperadmin.i18n import gettext as _

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.ext.asyncio import AsyncEngine
    from starlette.requests import Request


async def login_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    admin_prefix: str,
) -> Any:
    """Handle GET (render form) and POST (authenticate) for login."""
    error = None

    if request.method == "POST":
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        user = await auth_backend.authenticate(str(username), str(password))
        if user is not None:
            await auth_backend.login(request, user)
            return RedirectResponse(url=f"{admin_prefix}/", status_code=302)
        error = "Invalid username or password."

    context = {"request": request, "error": error, "admin_prefix": admin_prefix}
    return templates.TemplateResponse(request, "login.html", context)


async def logout_view(
    request: Request,
    auth_backend: Any,
    admin_prefix: str,
) -> RedirectResponse:
    """Handle POST logout — clear session and redirect to login."""
    await auth_backend.logout(request)
    return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)


# ── MFA challenge / verify / resend (C2-D, #486) ───────────────────────────


def _read_partial_auth(request: Request) -> dict[str, Any] | None:
    """Return the partial-auth marker if present and well-shaped, else None.

    Per the SDD's resolved Open Question #2, the marker is a structured dict
    ``{"stage": "mfa_pending", "user_id": <int>}``. Anything else (a stale
    bare-int from earlier drafts, or a corrupted entry) is treated as absent.
    """
    raw = request.session.get(PARTIAL_AUTH_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    if raw.get("stage") != "mfa_pending":
        return None
    if not isinstance(raw.get("user_id"), int):
        return None
    return raw


async def _load_partial_user(engine: AsyncEngine, user_id: int) -> User | None:
    async with AsyncSession(engine) as session:
        stmt = select(User).where(User.id == user_id)
        return (await session.execute(stmt)).scalar_one_or_none()


def _entry_is_expired(entry: dict[str, Any], otp_service: Any) -> bool:
    """Return True if a session OTP entry is past its TTL.

    Mirrors the TTL math inside ``EmailOTPService.verify`` so the view can
    surface a distinct "expired" message without depending on the service's
    return value (which collapses expiry and mismatch into False).
    """
    ttl = getattr(otp_service, "_ttl_seconds", 300)
    raw_issued_at = entry.get("issued_at")
    if not isinstance(raw_issued_at, str):
        return True
    try:
        issued_at = datetime.fromisoformat(raw_issued_at)
    except ValueError:
        return True
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) - issued_at > timedelta(seconds=ttl)


def _challenge_response(
    request: Request,
    templates: Jinja2Templates,
    admin_prefix: str,
    *,
    error: str | None = None,
    flash: str | None = None,
    expired: bool = False,
    status_code: int = 200,
) -> Any:
    """Render the MFA challenge template with optional error/flash state."""
    context = {
        "request": request,
        "admin_prefix": admin_prefix,
        "error": error,
        "flash": flash,
        "expired": expired,
    }
    return templates.TemplateResponse(
        request,
        "auth/mfa_challenge.html",
        context,
        status_code=status_code,
    )


async def mfa_challenge_view(
    request: Request,
    templates: Jinja2Templates,
    admin_prefix: str,
) -> Any:
    """GET /admin/mfa/challenge — render the OTP entry form.

    Requires a partial-auth session. If absent, the user is bounced to
    ``/admin/login`` — there is no useful challenge for an anonymous
    visitor and silently rendering the form would mislead them.
    """
    partial = _read_partial_auth(request)
    if partial is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)
    return _challenge_response(request, templates, admin_prefix)


async def mfa_verify_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    otp_service: Any,
    admin_prefix: str,
) -> Any:
    """POST /admin/mfa/verify — validate the submitted code, upgrade session.

    On success: clear ``PARTIAL_AUTH_SESSION_KEY`` BEFORE granting the full
    session via ``auth_backend.login``. The order matters: burning the
    partial marker first ensures any race between concurrent requests
    cannot escalate a partial-auth cookie into full auth.
    """
    partial = _read_partial_auth(request)
    if partial is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    user = await _load_partial_user(auth_backend.engine, partial["user_id"])
    if user is None:
        # User was deleted between password and MFA — drop them back to login.
        request.session.pop(PARTIAL_AUTH_SESSION_KEY, None)
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    form = await request.form()
    submitted = str(form.get("code", "")).strip()

    # Detect expiry / missing-entry states BEFORE delegating to ``verify`` so
    # we can render distinct error copy ("Code expired" vs "Invalid code").
    # ``EmailOTPService.verify`` collapses both into a False return — that is
    # correct for the service contract, but the user-facing template needs
    # to know which path to render (expired → highlight resend).
    entry = request.session.get(OTP_SESSION_KEY)
    if entry is None:
        return _challenge_response(
            request,
            templates,
            admin_prefix,
            error=_("Code expired, please request a new one."),
            expired=True,
        )
    if _entry_is_expired(entry, otp_service):
        return _challenge_response(
            request,
            templates,
            admin_prefix,
            error=_("Code expired, please request a new one."),
            expired=True,
        )

    ok = await otp_service.verify(user, submitted, request.session)
    if ok:
        # Clear partial marker FIRST, then grant full auth — see docstring.
        request.session.pop(PARTIAL_AUTH_SESSION_KEY, None)
        await auth_backend.login(request, user)
        return RedirectResponse(url=f"{admin_prefix}/", status_code=302)

    return _challenge_response(
        request,
        templates,
        admin_prefix,
        error=_("Invalid code."),
    )


async def mfa_resend_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    otp_service: Any,
    admin_prefix: str,
) -> Any:
    """POST /admin/mfa/resend — re-issue an OTP, rate-limited.

    Designed for HTMX (``hx-post``) so the surrounding challenge page
    stays put and only the flash region is swapped. Falling back to a
    plain form-POST also works: the full page re-renders with the flash.
    """
    partial = _read_partial_auth(request)
    if partial is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    user = await _load_partial_user(auth_backend.engine, partial["user_id"])
    if user is None:
        request.session.pop(PARTIAL_AUTH_SESSION_KEY, None)
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    try:
        await otp_service.generate_and_send(user, request.session)
    except RateLimitError:
        return _challenge_response(
            request,
            templates,
            admin_prefix,
            error=_("Too many attempts, try again later."),
        )

    return _challenge_response(
        request,
        templates,
        admin_prefix,
        flash=_("A new code has been sent to your email."),
    )
