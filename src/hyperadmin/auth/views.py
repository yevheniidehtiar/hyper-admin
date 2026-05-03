"""Login, logout and MFA view handlers for HyperAdmin.

The MFA endpoints (``/mfa/challenge``, ``/mfa/verify``, ``/mfa/resend``)
were added in v0.5.1 (C2-D, #486). They consume the partial-auth marker
written under ``PARTIAL_AUTH_SESSION_KEY`` by ``login_view`` (C3-A). The
settings / enable / disable trio (C3-A, #487) is the in-app surface for
managing MFA per-user; it is guarded by full auth via the middleware
gate that lives in :mod:`hyperadmin.auth.middleware`.
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
    otp_service: Any | None = None,
) -> Any:
    """Handle GET (render form) and POST (authenticate) for login.

    On a successful POST:

    * If ``user.mfa_enabled`` and an ``otp_service`` is configured, write the
      structured partial-auth marker (per the SDD's resolved Open Question
      #2 — ``{"stage": "mfa_pending", "user_id": <int>}``), trigger an OTP
      delivery, and redirect to ``/admin/mfa/challenge``. The full session
      is NOT created yet — the partial marker is the *only* state.
    * Otherwise, fall through to the existing single-factor path:
      ``auth_backend.login(request, user)`` and redirect to ``/admin/``.

    On rate-limit (``RateLimitError``) we still write the partial marker so
    the user can resume after the cooldown — per the SDD's "Rate limit
    exceeded" edge case ("Login view does **not** rotate the partial-auth
    session — user can resume after the cooldown"). On email-send failure
    the OTP service rolls back the entry; we surface a generic error and
    do NOT promote the user to full auth.
    """
    error: str | None = None

    if request.method == "POST":
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

        user = await auth_backend.authenticate(str(username), str(password))
        if user is not None:
            if user.mfa_enabled and otp_service is not None and user.id is not None:
                # Write the partial marker BEFORE attempting delivery so the
                # session reflects the in-flight state even when the email
                # send is slow. RateLimitError is non-fatal: the marker is
                # kept so the user can hit /mfa/resend after the cooldown.
                # Other exceptions from the sender are caught and surfaced
                # as a generic login error; the OTP service has already
                # rolled back its session entry.
                request.session[PARTIAL_AUTH_SESSION_KEY] = {
                    "stage": "mfa_pending",
                    "user_id": user.id,
                }
                try:
                    await otp_service.generate_and_send(user, request.session)
                except RateLimitError:
                    # Surface a recoverable state — the challenge page itself
                    # will show the rate-limit copy on next /resend.
                    pass
                except Exception:
                    # Email send failed; clear the partial marker so the
                    # user is not stranded mid-flow and re-prompt for login.
                    request.session.pop(PARTIAL_AUTH_SESSION_KEY, None)
                    error = _("Could not send verification code. Please try again.")
                    fail_context: dict[str, Any] = {
                        "request": request,
                        "error": error,
                        "admin_prefix": admin_prefix,
                    }
                    return templates.TemplateResponse(request, "login.html", fail_context)
                return RedirectResponse(url=f"{admin_prefix}/mfa/challenge", status_code=302)
            await auth_backend.login(request, user)
            return RedirectResponse(url=f"{admin_prefix}/", status_code=302)
        error = "Invalid username or password."

    context: dict[str, Any] = {
        "request": request,
        "error": error,
        "admin_prefix": admin_prefix,
    }
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


# ── MFA settings / enable / disable (C3-A, #487) ───────────────────────────
#
# These three endpoints are the in-app surface for managing per-user MFA.
# They require FULL auth — the partial-auth gate in middleware.py rewrites
# any partial-auth visit to ``/admin/mfa/challenge`` first, so by the time a
# request lands here ``request.state.user`` is guaranteed populated.
#
# The "disable" flow requires a fresh OTP confirmation per the SDD's
# defense-in-depth requirement ("Disable flow requires a fresh OTP
# confirmation"). The "enable" flow uses the same confirm-with-OTP pattern
# so a single shared template element can drive both states.


# Session key holding the in-flight settings flow ("enable" or "disable").
# Distinct from PARTIAL_AUTH_SESSION_KEY because settings flows happen
# while the user is FULLY authenticated; mixing the two keys would either
# spuriously trip the middleware gate or risk a race where a settings OTP
# could be used to skip the login challenge.
MFA_SETTINGS_FLOW_KEY = "mfa_settings_flow"


def _settings_response(
    request: Request,
    templates: Jinja2Templates,
    admin_prefix: str,
    user: User,
    *,
    flow: str | None = None,
    error: str | None = None,
    flash: str | None = None,
    status_code: int = 200,
) -> Any:
    """Render ``auth/mfa_settings.html`` with the current user state.

    ``flow`` is one of ``None`` / ``"enable"`` / ``"disable"`` and drives
    whether the inline OTP confirm input is rendered.
    """
    context = {
        "request": request,
        "admin_prefix": admin_prefix,
        "user": user,
        "flow": flow,
        "error": error,
        "flash": flash,
    }
    return templates.TemplateResponse(
        request,
        "auth/mfa_settings.html",
        context,
        status_code=status_code,
    )


def _current_user(request: Request) -> User | None:
    """Return the fully-authenticated user from request state, or None."""
    user = getattr(request.state, "user", None)
    if isinstance(user, User):
        return user
    return None


async def _persist_mfa_state(
    engine: AsyncEngine, user_id: int, *, enabled: bool, method: str | None
) -> User | None:
    """Update ``mfa_enabled`` / ``mfa_method`` for ``user_id`` and return the row."""
    async with AsyncSession(engine) as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            return None
        user.mfa_enabled = enabled
        user.mfa_method = method
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def mfa_settings_view(
    request: Request,
    templates: Jinja2Templates,
    admin_prefix: str,
) -> Any:
    """GET /admin/mfa/settings — show current MFA state for the logged-in user.

    Auth is enforced upstream by the middleware gate; if we reach this view,
    the user is fully authenticated.
    """
    user = _current_user(request)
    if user is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)
    return _settings_response(request, templates, admin_prefix, user)


async def mfa_enable_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    otp_service: Any,
    admin_prefix: str,
) -> Any:
    """POST /admin/mfa/enable — two-step enable flow.

    Step 1 (no ``code`` in form): send an OTP to the user's email and render
    the settings page with the inline confirm input.

    Step 2 (``code`` present in form): verify the OTP. On success flip
    ``mfa_enabled=True`` / ``mfa_method="email"`` and clear the flow marker.
    """
    user = _current_user(request)
    if user is None or user.id is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    form = await request.form()
    submitted = str(form.get("code", "")).strip()

    if not submitted:
        # Step 1: kick off the flow.
        request.session[MFA_SETTINGS_FLOW_KEY] = "enable"
        try:
            await otp_service.generate_and_send(user, request.session)
        except RateLimitError:
            return _settings_response(
                request,
                templates,
                admin_prefix,
                user,
                flow="enable",
                error=_("Too many attempts, try again later."),
            )
        return _settings_response(request, templates, admin_prefix, user, flow="enable")

    # Step 2: verify the submitted OTP. Confirm we're still in an enable
    # flow — defense in depth against form replay across flows.
    if request.session.get(MFA_SETTINGS_FLOW_KEY) != "enable":
        return _settings_response(
            request,
            templates,
            admin_prefix,
            user,
            error=_("No active MFA enable flow. Please try again."),
        )

    ok = await otp_service.verify(user, submitted, request.session)
    if not ok:
        return _settings_response(
            request,
            templates,
            admin_prefix,
            user,
            flow="enable",
            error=_("Invalid code."),
        )

    # Successful verify — flip the flag in the DB, clear the flow marker,
    # then render the settings page reflecting the new state.
    updated = await _persist_mfa_state(auth_backend.engine, user.id, enabled=True, method="email")
    request.session.pop(MFA_SETTINGS_FLOW_KEY, None)
    return _settings_response(
        request,
        templates,
        admin_prefix,
        updated or user,
        flash=_("Two-factor authentication enabled."),
    )


async def mfa_disable_view(
    request: Request,
    templates: Jinja2Templates,
    auth_backend: Any,
    otp_service: Any,
    admin_prefix: str,
) -> Any:
    """POST /admin/mfa/disable — two-step disable flow with confirmation.

    Per the SDD's defense-in-depth requirement, disable always requires a
    fresh OTP — clicking "Disable" sends a new code; submitting it flips
    ``mfa_enabled=False``.
    """
    user = _current_user(request)
    if user is None or user.id is None:
        return RedirectResponse(url=f"{admin_prefix}/login", status_code=302)

    form = await request.form()
    submitted = str(form.get("code", "")).strip()

    if not submitted:
        request.session[MFA_SETTINGS_FLOW_KEY] = "disable"
        try:
            await otp_service.generate_and_send(user, request.session)
        except RateLimitError:
            return _settings_response(
                request,
                templates,
                admin_prefix,
                user,
                flow="disable",
                error=_("Too many attempts, try again later."),
            )
        return _settings_response(request, templates, admin_prefix, user, flow="disable")

    if request.session.get(MFA_SETTINGS_FLOW_KEY) != "disable":
        return _settings_response(
            request,
            templates,
            admin_prefix,
            user,
            error=_("No active MFA disable flow. Please try again."),
        )

    ok = await otp_service.verify(user, submitted, request.session)
    if not ok:
        return _settings_response(
            request,
            templates,
            admin_prefix,
            user,
            flow="disable",
            error=_("Invalid code."),
        )

    updated = await _persist_mfa_state(auth_backend.engine, user.id, enabled=False, method=None)
    request.session.pop(MFA_SETTINGS_FLOW_KEY, None)
    return _settings_response(
        request,
        templates,
        admin_prefix,
        updated or user,
        flash=_("Two-factor authentication disabled."),
    )
