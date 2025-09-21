import re
from playwright.sync_api import Page, expect

def test_create_view_loads(page: Page, demo_base_url: str) -> None:
    """Test that the create view loads correctly."""
    page.goto(demo_base_url + "/admin/user/create")

    expect(page).to_have_title(re.compile("Create User"))

    save_button = page.get_by_role("button", name="Save")
    expect(save_button).to_be_visible()

def test_create_view_form_fields(page: Page, demo_base_url: str) -> None:
    """Test that the create view form displays fields."""
    page.goto(demo_base_url + "/admin/user/create")

    expect(page.get_by_label("Name")).to_be_visible()
    expect(page.get_by_label("Email")).to_be_visible()
