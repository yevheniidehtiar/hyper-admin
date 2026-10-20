"""E2E: a plugin's page, sidebar entry and static files inside the admin.

SDD ``docs/specs/plugin-registry.md`` (phase 1b). Runs against
:mod:`tests.e2e.apps.plugin_registry`, which registers the test-only demo plugin.
Uses accessibility-first selectors per CLAUDE.md E2E Selector Convention.
"""

from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_plugin_nav_entry_opens_the_plugin_page_for_permitted_users(
    page: Page, plugin_base_url: str
) -> None:
    """Scenario: plugin nav entry appears in the sidebar for permitted users only."""
    # Given the demo plugin adds "Demo report" gated on view_demo_report
    # And superuser alice is signed in
    _login(page, plugin_base_url, "alice")
    css_responses: list[int] = []
    page.on(
        "response",
        lambda r: css_responses.append(r.status) if r.url.endswith("/demo.css") else None,
    )

    # When she follows the sidebar link
    nav_link = page.get_by_test_id("sidebar-plugin-demo-demo-index")
    expect(nav_link).to_be_visible()
    nav_link.click()

    # Then the plugin page renders inside the admin layout with its own stylesheet
    expect(page).to_have_url(f"{plugin_base_url}/admin/demo/")
    expect(page.get_by_role("heading", name="Demo report")).to_be_visible()
    expect(page.get_by_test_id("sidebar")).to_be_visible()
    expect(nav_link).to_have_attribute("aria-current", "page")
    assert css_responses == [200]


def test_plugin_nav_entry_is_hidden_without_the_permission(
    page: Page, plugin_base_url: str
) -> None:
    """Scenario: a user without the plugin permission sees no entry and no page."""
    # Given bob, who lacks view_demo_report, is signed in
    _login(page, plugin_base_url, "bob")

    # When he looks at the sidebar
    # Then the plugin entry is not rendered
    expect(page.get_by_test_id("sidebar")).to_be_visible()
    expect(page.get_by_test_id("sidebar-plugin-demo-demo-index")).to_have_count(0)

    # And opening the page directly is refused inside the admin layout
    response = page.goto(f"{plugin_base_url}/admin/demo/")
    assert response is not None
    assert response.status == 403
    expect(page.get_by_test_id("error-page")).to_be_visible()
