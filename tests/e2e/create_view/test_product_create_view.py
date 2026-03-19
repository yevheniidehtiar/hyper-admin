import re

from playwright.sync_api import Page, expect


def test_create_product_form_rendering(page: Page, demo_base_url: str):
    """Test that the create form for Product model is rendered correctly."""
    page.goto(f"{demo_base_url}/admin/product/create")
    expect(page).to_have_title("HyperAdmin")
    h2 = page.locator("main").locator("h2")
    expect(h2).to_be_visible()
    expect(h2).to_have_text("Create Product")
    expect(page.locator(f'form[hx-post="{demo_base_url}/admin/product"]')).to_be_visible()

    # Text input for name
    expect(page.locator('label[for="name"]')).to_have_text("Name*")
    expect(page.locator('input[name="name"]')).to_be_visible()

    # Textarea for description
    expect(page.locator('label[for="description"]')).to_have_text("Description*")
    expect(page.locator('textarea[name="description"]')).to_be_visible()

    # Number input for price
    expect(page.locator('label[for="price"]')).to_have_text("Price*")
    expect(page.locator('input[name="price"][type="number"]')).to_be_visible()

    # Checkbox for is_available
    expect(page.locator('label[for="is_available"]')).to_have_text("Is available*")
    expect(page.locator('input[name="is_available"][type="checkbox"]')).to_be_visible()

    # Select for category
    expect(page.locator('label[for="category"]')).to_have_text("Category*")
    expect(page.locator('select[name="category"]')).to_be_visible()
    expect(page.locator('select[name="category"] option')).to_have_count(3)

    # Submit button
    expect(page.locator('button[type="submit"]')).to_have_text("Create")


def test_create_product_validation_error(page: Page, demo_base_url: str):
    """Test that submitting an invalid form for Product model shows an error message."""
    page.goto(f"{demo_base_url}/admin/product/create")
    page.locator('input[name="name"]').fill("")
    page.locator('button[type="submit"]').click()
    validation_error = page.locator('input[name="name"] ~ ul.ha-field-errors')
    expect(validation_error).to_be_visible()
    expect(validation_error).to_contain_text("String should have at least 1 character")


def test_create_product_successful_submission(page: Page, demo_base_url: str):
    """Test that successful submission for Product model redirects to the detail page."""
    page.goto(f"{demo_base_url}/admin/product/create")

    page.locator('input[name="name"]').fill("Test Product")
    page.locator('textarea[name="description"]').fill("A great product")
    page.locator('input[name="price"]').fill("12.34")
    page.locator('input[name="is_available"]').check()
    page.locator('select[name="category"]').select_option("BOOKS")

    page.locator('button[type="submit"]').click()

    # The redirect is handled by HTMX, so we need to wait for the URL to change.
    expect(page).to_have_url(re.compile(r".*/admin/product/\d+"))
    expect(page.get_by_role("heading", name=re.compile(r"Product #"))).to_contain_text("Product #")
    expect(page.locator(".detail-fields")).to_contain_text("Test Product")
    expect(page.locator(".detail-fields")).to_contain_text("A great product")
    expect(page.locator(".detail-fields")).to_contain_text("12.34")
    expect(page.locator(".detail-fields")).to_contain_text("True")
    expect(page.locator(".detail-fields")).to_contain_text("ProductCategory.BOOKS")
