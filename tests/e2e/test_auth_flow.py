"""E2E tests for the full authentication lifecycle (#362).

Covers: login redirect, valid/invalid credentials, protected model access,
sidebar auth model visibility, logout, and post-logout redirect.

Uses accessibility-first selectors per CLAUDE.md E2E Selector Convention.
"""

from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str, password: str = "secret123") -> None:
    """Log in as alice with the given password."""
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill("alice")
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def _logout(page: Page) -> None:
    """Open the user menu dropdown and click Logout."""
    page.locator("button[aria-haspopup='true']").click()
    page.get_by_test_id("logout-btn").click()


def test_unauthenticated_redirects_to_login(page: Page, auth_base_url: str) -> None:
    """Unauthenticated GET /admin/ redirects to /admin/login."""
    # Given no session cookie is present
    # When GET /admin/ is requested
    page.goto(f"{auth_base_url}/admin/")

    # Then the browser ends up on the login page
    expect(page).to_have_url(f"{auth_base_url}/admin/login")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()


def test_valid_credentials_login(page: Page, auth_base_url: str) -> None:
    """Valid credentials grant session and redirect to dashboard."""
    # Given a superuser alice exists with password secret123
    # When POST /admin/login with correct credentials
    _login(page, auth_base_url)

    # Then the response redirects to /admin/
    expect(page).to_have_url(f"{auth_base_url}/admin/")


def test_invalid_credentials_error(page: Page, auth_base_url: str) -> None:
    """Invalid credentials re-render login with error message."""
    # Given a superuser alice exists with password secret123
    # When POST /admin/login with wrong password
    _login(page, auth_base_url, password="wrong")

    # Then the login page is re-rendered with an error
    expect(page).to_have_url(f"{auth_base_url}/admin/login")
    expect(page.get_by_text("Invalid username or password.")).to_be_visible()

    # And the sign-in button is still visible (form re-rendered)
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()


def test_authenticated_user_views_protected_model(page: Page, auth_base_url: str) -> None:
    """Authenticated user can view a protected model list."""
    # Given alice is logged in as superuser
    _login(page, auth_base_url)

    # When GET /admin/user is requested
    page.goto(f"{auth_base_url}/admin/user")

    # Then the list view for User is rendered
    expect(page).to_have_url(f"{auth_base_url}/admin/user")
    expect(page.get_by_role("heading", name="UserList")).to_be_visible()


def test_auth_models_in_sidebar(page: Page, auth_base_url: str) -> None:
    """Auth models visible in sidebar after auto-registration."""
    # Given alice is logged in as superuser
    _login(page, auth_base_url)

    # When viewing the admin dashboard
    sidebar = page.get_by_test_id("sidebar")

    # Then the sidebar contains User, Group, and Permission
    expect(sidebar.get_by_text("User")).to_be_visible()
    expect(sidebar.get_by_text("Group")).to_be_visible()
    expect(sidebar.get_by_text("Permission")).to_be_visible()


def test_logout_clears_session(page: Page, auth_base_url: str) -> None:
    """Logout clears session and redirects to login."""
    # Given alice is logged in
    _login(page, auth_base_url)
    expect(page).to_have_url(f"{auth_base_url}/admin/")

    # When POST /admin/logout is requested
    _logout(page)

    # Then the session is cleared and user is redirected to login
    expect(page).to_have_url(f"{auth_base_url}/admin/login")


def test_post_logout_redirect(page: Page, auth_base_url: str) -> None:
    """Post-logout access is redirected to login."""
    # Given alice has just logged out
    _login(page, auth_base_url)
    _logout(page)
    expect(page).to_have_url(f"{auth_base_url}/admin/login")

    # When GET /admin/ is requested
    page.goto(f"{auth_base_url}/admin/")

    # Then the response redirects to /admin/login
    expect(page).to_have_url(f"{auth_base_url}/admin/login")
