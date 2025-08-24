from playwright.sync_api import Page, expect


def test_delete_item_with_confirmation(page: Page, demo_base_url: str) -> None:
    """Tests that deleting an item shows a confirmation dialog and works correctly."""

    # Handle the confirmation dialog
    page.on("dialog", lambda dialog: dialog.accept())

    page.goto(demo_base_url + "/admin/user/")

    # Get the number of rows before deleting
    initial_row_count = page.locator("tbody tr").count()

    # Click the delete button on the first user
    page.locator("tbody tr:first-child >> text=Delete").click()

    # Wait for the row to be removed
    expect(page.locator("tbody tr")).to_have_count(initial_row_count - 1)
