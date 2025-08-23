from playwright.sync_api import Page, expect


def test_open_admin_home_page(page: Page, demo_base_url: str) -> None:
    """Smoke test: Admin dashboard renders using shared E2E fixtures."""

    page.goto(demo_base_url + "/")
    # Basic smoke assertion with auto-waiting
    expect(page.get_by_text("Go to /admin/user").first).to_be_visible()
