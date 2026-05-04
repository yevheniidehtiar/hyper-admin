"""End-to-end tests for the MVP email-OTP MFA flow (C3-C, #488).

Each test maps 1:1 to a Track B BDD scenario in
``docs/specs/object-permissions-mfa.md``. Inline ``# Given / # When / # Then``
comments are mandatory per ``.claude/rules/bdd-conventions.md``.

Selectors follow the CLAUDE.md E2E Selector Convention — accessibility-first
with ``data-testid`` for elements without a natural role. The test app
served by the ``mfa_base_url`` fixture exposes three test-only endpoints:

* ``POST /_test/reset_otp_state`` — wipe captured codes + session state
* ``GET  /_test/latest_code?email=`` — read the most recent OTP for that email
* ``POST /_test/backdate_session_otp`` — backdate session OTP past its TTL

These are HTTP helpers, not selectors — they let the Playwright test read
the code that the in-process server just generated and drive expiry
without sleeping for the full TTL.
"""

from __future__ import annotations

import requests
from playwright.sync_api import Page, expect

# ── Shared helpers ────────────────────────────────────────────────────────


def _reset(base_url: str, page: Page) -> None:
    """Wipe both server-side capture history and the browser's cookies.

    Must be called at the START of every scenario — the test app's user
    fixtures are shared across the uvicorn process lifetime, but per-test
    isolation requires a clean session cookie + a clean OTP capture log.
    """
    page.context.clear_cookies()
    requests.post(f"{base_url}/_test/reset_otp_state", timeout=2)


def _latest_code(base_url: str, email: str) -> str:
    """Return the most recent OTP code captured for ``email`` (server-side)."""
    resp = requests.get(f"{base_url}/_test/latest_code", params={"email": email}, timeout=2)
    resp.raise_for_status()
    code = resp.json().get("code")
    assert code, f"no OTP captured for {email}"
    return str(code)


def _submit_password(page: Page, base_url: str, username: str, password: str) -> None:
    """Submit the login form for ``username`` / ``password``."""
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


# ── Scenario: MFA-disabled user logs in with one factor ───────────────────


def test_mfa_disabled_user_logs_in_with_one_factor(page: Page, mfa_base_url: str) -> None:
    """Bob (mfa_enabled=False) skips the MFA challenge entirely."""
    # Given bob exists with mfa_enabled=False
    _reset(mfa_base_url, page)

    # When bob submits correct credentials
    _submit_password(page, mfa_base_url, "bob", "secret")

    # Then he lands directly on the admin dashboard (no MFA challenge)
    expect(page).to_have_url(f"{mfa_base_url}/admin/")


# ── Scenario: MFA-enabled user is redirected to challenge after password ──


def test_mfa_enabled_user_is_redirected_to_challenge_after_password(
    page: Page, mfa_base_url: str
) -> None:
    """Alice (mfa_enabled=True) is bounced to the MFA challenge."""
    # Given alice exists with mfa_enabled=True
    _reset(mfa_base_url, page)

    # When alice submits her correct password
    _submit_password(page, mfa_base_url, "alice", "secret")

    # Then she lands on the MFA challenge page (partial-auth)
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")
    expect(page.get_by_test_id("mfa-code-input")).to_be_visible()
    expect(page.get_by_test_id("mfa-verify-btn")).to_be_visible()


# ── Scenario: correct OTP code completes login ────────────────────────────


def test_correct_otp_code_completes_login(page: Page, mfa_base_url: str) -> None:
    """Submitting the correct OTP upgrades partial-auth to a full session."""
    # Given alice has just passed the password step
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")

    # When she enters the issued OTP and submits
    code = _latest_code(mfa_base_url, "alice@example.com")
    page.get_by_test_id("mfa-code-input").fill(code)
    page.get_by_test_id("mfa-verify-btn").click()

    # Then she is redirected to the admin dashboard with a full session
    expect(page).to_have_url(f"{mfa_base_url}/admin/")


# ── Scenario: wrong OTP code shows an error ───────────────────────────────


def test_wrong_otp_code_shows_an_error(page: Page, mfa_base_url: str) -> None:
    """A wrong code re-renders the challenge with an error and keeps partial-auth."""
    # Given alice has passed the password step
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")

    # When she submits a wrong code
    page.get_by_test_id("mfa-code-input").fill("000000")
    page.get_by_test_id("mfa-verify-btn").click()

    # Then the challenge re-renders with an "Invalid code" error.
    # The verify endpoint returns 200 (re-rendered template) so the URL
    # stays at /admin/mfa/verify; we assert on the visible error + the
    # code input still being present (proves we are still on the form).
    expect(page.get_by_test_id("mfa-error")).to_be_visible()
    expect(page.get_by_test_id("mfa-error")).to_contain_text("Invalid")
    expect(page.get_by_test_id("mfa-code-input")).to_be_visible()


# ── Scenario: expired OTP code shows error with resend option ─────────────


def test_expired_otp_code_shows_error_with_resend_option(page: Page, mfa_base_url: str) -> None:
    """An expired code shows the "expired" copy and a resend affordance."""
    # Given alice's OTP entry has been backdated past its TTL
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")
    issued_code = _latest_code(mfa_base_url, "alice@example.com")
    # Backdate via the test endpoint from inside the browser context so
    # the session cookie is sent automatically. Using ``requests`` from
    # the test process loses the session cookie set by Starlette's
    # SessionMiddleware (the cookie is HTTPOnly + the request library
    # doesn't share the browser jar transparently).
    backdate_status = page.evaluate(
        """async (url) => {
            const resp = await fetch(url, { method: 'POST', credentials: 'include' });
            return resp.status;
        }""",
        f"{mfa_base_url}/_test/backdate_session_otp",
    )
    assert backdate_status == 204

    # When she submits the (now expired) code
    page.get_by_test_id("mfa-code-input").fill(issued_code)
    page.get_by_test_id("mfa-verify-btn").click()

    # Then the page shows an "expired" message and the resend link is visible
    expect(page.get_by_test_id("mfa-error")).to_be_visible()
    expect(page.get_by_test_id("mfa-error")).to_contain_text("expired")
    expect(page.get_by_test_id("mfa-resend-link")).to_be_visible()


# ── Scenario: rate limit blocks excessive OTP requests ────────────────────


def test_rate_limit_blocks_excessive_otp_requests(page: Page, mfa_base_url: str) -> None:
    """Repeated resends trigger the rate-limit message in the UI.

    The test app configures the OTP service with ``rate_limit=(2, 3600)``;
    one code is issued at login, a second at the first resend, and the
    third resend within the same session must surface the rate-limit copy.
    """
    # Given alice is on the MFA challenge page after a successful password
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")

    # When she clicks "Resend code" twice in a row to exhaust the budget
    page.get_by_test_id("mfa-resend-link").click()
    # The first resend renders a flash; wait for it before the next click.
    expect(page.get_by_test_id("mfa-flash")).to_be_visible()
    page.get_by_test_id("mfa-resend-link").click()

    # Then the rate-limit error surfaces (matches the SDD's "Too many attempts" copy)
    expect(page.get_by_test_id("mfa-error")).to_be_visible()
    expect(page.get_by_test_id("mfa-error")).to_contain_text("Too many attempts")


# ── Scenario: partial-auth session cannot reach admin routes ──────────────


def test_partial_auth_session_cannot_reach_admin_routes(page: Page, mfa_base_url: str) -> None:
    """The middleware bounces partial-auth users from admin to /mfa/challenge."""
    # Given alice has only completed the password step
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")

    # When she navigates to a regular admin route (the user list is always present)
    page.goto(f"{mfa_base_url}/admin/user")

    # Then the partial-auth gate redirects her back to the MFA challenge
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")


# ── Scenario: enable MFA from settings ────────────────────────────────────


def test_enable_mfa_from_settings(page: Page, mfa_base_url: str) -> None:
    """Bob (MFA off) enables MFA from the settings page via OTP confirmation."""
    # Given bob is fully authenticated and visits /admin/mfa/settings
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "bob", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/")
    page.goto(f"{mfa_base_url}/admin/mfa/settings")
    expect(page.get_by_test_id("mfa-status-indicator")).to_have_attribute(
        "data-mfa-enabled", "false"
    )

    # When he clicks "Enable" — Step 1 of the flow sends an OTP
    page.get_by_test_id("mfa-enable-btn").click()
    expect(page.get_by_test_id("mfa-confirm-input")).to_be_visible()
    enable_code = _latest_code(mfa_base_url, "bob@example.com")

    # And he submits the OTP from his email — Step 2 flips the flag
    page.get_by_test_id("mfa-confirm-input").fill(enable_code)
    page.get_by_test_id("mfa-confirm-btn").click()

    # Then the settings page reports MFA is now enabled
    expect(page.get_by_test_id("mfa-status-indicator")).to_have_attribute(
        "data-mfa-enabled", "true"
    )


# ── Scenario: disable MFA from settings ───────────────────────────────────


def test_disable_mfa_from_settings(page: Page, mfa_base_url: str) -> None:
    """Alice (MFA on) disables MFA from settings after confirming a fresh OTP."""
    # Given alice is fully authenticated (login + verify OTP)
    _reset(mfa_base_url, page)
    _submit_password(page, mfa_base_url, "alice", "secret")
    expect(page).to_have_url(f"{mfa_base_url}/admin/mfa/challenge")
    login_code = _latest_code(mfa_base_url, "alice@example.com")
    page.get_by_test_id("mfa-code-input").fill(login_code)
    page.get_by_test_id("mfa-verify-btn").click()
    expect(page).to_have_url(f"{mfa_base_url}/admin/")

    # And visits the MFA settings page
    page.goto(f"{mfa_base_url}/admin/mfa/settings")
    expect(page.get_by_test_id("mfa-status-indicator")).to_have_attribute(
        "data-mfa-enabled", "true"
    )

    # When she clicks "Disable" — Step 1 sends a fresh confirmation OTP
    page.get_by_test_id("mfa-disable-btn").click()
    expect(page.get_by_test_id("mfa-confirm-input")).to_be_visible()
    disable_code = _latest_code(mfa_base_url, "alice@example.com")

    # And she submits the disable confirmation code — Step 2 flips the flag
    page.get_by_test_id("mfa-confirm-input").fill(disable_code)
    page.get_by_test_id("mfa-confirm-btn").click()

    # Then the settings page reports MFA is now disabled
    expect(page.get_by_test_id("mfa-status-indicator")).to_have_attribute(
        "data-mfa-enabled", "false"
    )
