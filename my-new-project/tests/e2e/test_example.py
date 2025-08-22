import re
from playwright.sync_api import Page, expect

def test_example(page: Page):
    """
    A simple placeholder test to ensure the E2E setup is working.
    This test navigates to a page and checks its title.
    """
    page.goto("https://playwright.dev/")

    # Expect a title "to contain" a substring.
    expect(page).to_have_title(re.compile("Playwright"))
