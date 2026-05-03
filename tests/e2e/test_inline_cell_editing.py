"""End-to-end tests for inline cell editing in the list view.

One Playwright test per BDD scenario from
``docs/specs/inline-cell-editing.md``. The example ``UserAdmin`` declares
``list_editable = ["name", "is_active"]``.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def _first_user_row_id(page: Page) -> str:
    """Return the first User row's primary key as a string.

    The test seed creates users in a fixed order (Alice first), so the cell
    test ids are derived deterministically. We read the id from the View
    link's href to avoid hard-coding it.
    """
    view = page.get_by_test_id("row-view-link").first
    href = view.get_attribute("href") or ""
    return href.rsplit("/", 1)[-1]


def test_editable_cell_renders_an_edit_affordance(page: Page, demo_base_url: str) -> None:
    # Given the User model declares list_editable = ["name", "is_active"]
    page.goto(demo_base_url + "/admin/user")

    # When the user opens the list view
    pk = _first_user_row_id(page)

    # Then editable cells contain a cell-edit-{field}-{id} button
    expect(page.get_by_test_id(f"cell-edit-name-{pk}")).to_be_visible()
    # And non-editable cells (e.g. email) do not contain such a button
    assert page.get_by_test_id(f"cell-edit-email-{pk}").count() == 0


def test_opening_the_editor_swaps_the_cell_to_an_inline_input(
    page: Page, demo_base_url: str
) -> None:
    # Given the user is on the list view
    page.goto(demo_base_url + "/admin/user")
    pk = _first_user_row_id(page)

    # When the user clicks the edit affordance on Alice's name cell
    page.get_by_test_id(f"cell-edit-name-{pk}").click()

    # Then the cell is replaced by an inline form with an input pre-filled
    editor = page.get_by_test_id(f"cell-editor-name-{pk}")
    expect(editor).to_be_visible()
    expect(page.get_by_test_id(f"cell-save-name-{pk}")).to_be_visible()
    expect(page.get_by_test_id(f"cell-cancel-name-{pk}")).to_be_visible()
    # And Save and Cancel buttons are present


def test_saving_a_valid_value_persists_and_re_renders_the_cell(
    page: Page, demo_base_url: str
) -> None:
    # Given the inline editor for Alice's name cell is open
    page.goto(demo_base_url + "/admin/user")
    pk = _first_user_row_id(page)
    page.get_by_test_id(f"cell-edit-name-{pk}").click()
    editor = page.get_by_test_id(f"cell-editor-name-{pk}")
    expect(editor).to_be_visible()

    name_input = page.get_by_role("textbox", name="Name", exact=True)
    name_input.fill("Alicia")

    # When the user clicks Save
    page.get_by_test_id(f"cell-save-name-{pk}").click()

    # Then the cell is re-rendered with the new value
    expect(page.get_by_test_id(f"cell-edit-name-{pk}")).to_be_visible()
    expect(page.get_by_test_id(f"cell-value-name-{pk}")).to_contain_text("Alicia")
    # And aria-live "saved" flag is present (visually hidden)
    expect(page.get_by_test_id(f"cell-saved-flag-name-{pk}")).to_be_attached()


def test_invalid_input_shows_error_fragment_without_persisting(
    page: Page, demo_base_url: str
) -> None:
    # Given the inline editor for Alice's name cell is open
    page.goto(demo_base_url + "/admin/user")
    pk = _first_user_row_id(page)
    original = page.get_by_test_id(f"cell-value-name-{pk}").text_content() or ""
    page.get_by_test_id(f"cell-edit-name-{pk}").click()
    expect(page.get_by_test_id(f"cell-editor-name-{pk}")).to_be_visible()

    # When the user clears the input and clicks Save
    name_input = page.get_by_role("textbox", name="Name", exact=True)
    name_input.fill("")
    page.get_by_test_id(f"cell-save-name-{pk}").click()

    # Then the cell shows a field-error list
    expect(page.get_by_test_id("name-errors")).to_be_visible()

    # And the original value is still in the database — cancel and verify
    page.get_by_test_id(f"cell-cancel-name-{pk}").click()
    expect(page.get_by_test_id(f"cell-value-name-{pk}")).to_have_text(original)


def test_cancelling_restores_the_static_cell(page: Page, demo_base_url: str) -> None:
    # Given the inline editor for Alice's name cell is open
    page.goto(demo_base_url + "/admin/user")
    pk = _first_user_row_id(page)
    original = page.get_by_test_id(f"cell-value-name-{pk}").text_content() or ""
    page.get_by_test_id(f"cell-edit-name-{pk}").click()
    expect(page.get_by_test_id(f"cell-editor-name-{pk}")).to_be_visible()

    # Mutate the input but DON'T save
    page.get_by_role("textbox", name="Name", exact=True).fill("DRAFT — should not persist")

    # When the user clicks Cancel
    page.get_by_test_id(f"cell-cancel-name-{pk}").click()

    # Then the cell is restored to its read-only form with the original value
    expect(page.get_by_test_id(f"cell-edit-name-{pk}")).to_be_visible()
    expect(page.get_by_test_id(f"cell-value-name-{pk}")).to_have_text(original)


def test_non_editable_field_cannot_be_posted_inline(page: Page, demo_base_url: str) -> None:
    # Given the User model does NOT declare email as list_editable
    pk = "1"
    # When a POST is sent to the inline endpoint for email
    response = page.request.post(
        f"{demo_base_url}/admin/user/{pk}/inline/email",
        form={"email": "evil@example.com"},
    )
    # Then the response status is 403
    assert response.status == 403


def test_keyboard_escape_cancels_the_editor(page: Page, demo_base_url: str) -> None:
    # Given the inline editor for the first user's name cell is open
    page.goto(demo_base_url + "/admin/user")
    pk = _first_user_row_id(page)
    original = page.get_by_test_id(f"cell-value-name-{pk}").text_content() or ""
    page.get_by_test_id(f"cell-edit-name-{pk}").click()
    expect(page.get_by_test_id(f"cell-editor-name-{pk}")).to_be_visible()

    # When the user presses Escape inside the input
    page.get_by_role("textbox", name="Name", exact=True).press("Escape")

    # Then the editor is cancelled and the static cell restored
    expect(page.get_by_test_id(f"cell-edit-name-{pk}")).to_be_visible()
    expect(page.get_by_test_id(f"cell-value-name-{pk}")).to_have_text(original)
