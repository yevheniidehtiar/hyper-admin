"""End-to-end tests for the light/dark theme toggle in the navbar."""

from playwright.sync_api import Page, expect

# The dashboard is always available regardless of which model-admin routes are registered.
_ADMIN_URL = "/admin/"


def test_theme_toggle_button_visible_in_navbar(page: Page, demo_base_url: str) -> None:
    """Theme toggle button is present in the navbar on all pages."""
    page.goto(demo_base_url + _ADMIN_URL)

    toggle = page.get_by_test_id("theme-toggle")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_attribute("aria-label", "Toggle dark mode")

    # Also verify it is inside the navbar
    navbar = page.get_by_role("navigation", name="Main navigation")
    expect(navbar.get_by_test_id("theme-toggle")).to_be_visible()


def test_clicking_toggle_activates_dark_mode(page: Page, demo_base_url: str) -> None:
    """Clicking the toggle adds ha-theme-dark class to <html>."""
    page.goto(demo_base_url + _ADMIN_URL)

    # Ensure we start from a light / non-dark state
    page.evaluate(
        "() => { "
        "document.documentElement.classList.remove('ha-theme-dark'); "
        "document.documentElement.classList.remove('ha-theme-light'); "
        "document.documentElement.removeAttribute('data-theme'); "
        "}"
    )

    toggle = page.get_by_test_id("theme-toggle")
    toggle.click()

    has_dark = page.evaluate("() => document.documentElement.classList.contains('ha-theme-dark')")
    assert has_dark, "Expected ha-theme-dark class on <html> after first toggle click"

    data_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    assert data_theme == "dark", f"Expected data-theme='dark', got {data_theme!r}"


def test_clicking_toggle_twice_reverts_to_light_mode(page: Page, demo_base_url: str) -> None:
    """Double-clicking the toggle removes ha-theme-dark class from <html>."""
    page.goto(demo_base_url + _ADMIN_URL)

    # Start from a known light state
    page.evaluate(
        "() => { "
        "document.documentElement.classList.remove('ha-theme-dark'); "
        "document.documentElement.classList.remove('ha-theme-light'); "
        "document.documentElement.removeAttribute('data-theme'); "
        "}"
    )

    toggle = page.get_by_test_id("theme-toggle")

    # First click → dark
    toggle.click()
    has_dark = page.evaluate("() => document.documentElement.classList.contains('ha-theme-dark')")
    assert has_dark, "Expected ha-theme-dark class after first click"

    # Second click → back to light
    toggle.click()
    has_dark_after = page.evaluate(
        "() => document.documentElement.classList.contains('ha-theme-dark')"
    )
    assert not has_dark_after, "Expected ha-theme-dark to be removed after second click"

    data_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    assert data_theme == "light", (
        f"Expected data-theme='light' after toggle back, got {data_theme!r}"
    )


def test_dark_mode_persists_across_navigation(page: Page, demo_base_url: str) -> None:
    """Dark mode preference is preserved when navigating to another page."""
    page.goto(demo_base_url + _ADMIN_URL)

    # Ensure we start from a light / non-dark state
    page.evaluate(
        "() => { "
        "document.documentElement.classList.remove('ha-theme-dark'); "
        "document.documentElement.classList.remove('ha-theme-light'); "
        "document.documentElement.removeAttribute('data-theme'); "
        "localStorage.removeItem('ha-theme'); "
        "}"
    )

    toggle = page.get_by_test_id("theme-toggle")
    toggle.click()

    # Confirm dark mode is active
    has_dark = page.evaluate("() => document.documentElement.classList.contains('ha-theme-dark')")
    assert has_dark, "Expected ha-theme-dark after toggle"

    # Navigate to root (a different page served by the same app)
    page.goto(demo_base_url + "/")
    page.go_back()
    page.wait_for_url(f"**{_ADMIN_URL}")

    # Theme should be restored from localStorage on the returned page
    has_dark_after_nav = page.evaluate(
        "() => document.documentElement.classList.contains('ha-theme-dark')"
    )
    assert has_dark_after_nav, "Expected ha-theme-dark to persist after navigation to a new page"

    # Clean up
    page.evaluate("() => localStorage.removeItem('ha-theme')")


def test_dark_mode_persists_on_page_reload(page: Page, demo_base_url: str) -> None:
    """Dark mode preference stored in localStorage survives page reload."""
    page.goto(demo_base_url + _ADMIN_URL)

    # Ensure we start from a light / non-dark state
    page.evaluate(
        "() => { "
        "document.documentElement.classList.remove('ha-theme-dark'); "
        "document.documentElement.classList.remove('ha-theme-light'); "
        "document.documentElement.removeAttribute('data-theme'); "
        "localStorage.removeItem('ha-theme'); "
        "}"
    )

    toggle = page.get_by_test_id("theme-toggle")
    toggle.click()

    # Confirm dark mode is active and stored
    has_dark = page.evaluate("() => document.documentElement.classList.contains('ha-theme-dark')")
    assert has_dark, "Expected ha-theme-dark after toggle"

    stored = page.evaluate("() => localStorage.getItem('ha-theme')")
    assert stored == "dark", f"Expected localStorage ha-theme='dark', got {stored!r}"

    # Reload the page — the inline theme-init script restores the class before CSS renders
    page.reload()

    has_dark_after_reload = page.evaluate(
        "() => document.documentElement.classList.contains('ha-theme-dark')"
    )
    assert has_dark_after_reload, (
        "Expected ha-theme-dark to be restored from localStorage after page reload"
    )

    # Clean up localStorage so this test does not bleed into others
    page.evaluate("() => localStorage.removeItem('ha-theme')")
