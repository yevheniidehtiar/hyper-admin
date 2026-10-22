"""Permission matrix UI (st-v057-pmx-03): grid, diff save, column select-all, conflict
banner, rejected cells, object-rule popover and the sidebar link, driven in the browser.

Scenarios come from ``docs/specs/permission-matrix-ui.md`` and the PermissionMatrix /
ObjectPermissionPopover designs. The fixture app is :mod:`tests.e2e.apps.permissions_matrix`:
superuser ``alice``, ``editor`` (holds the matrix codename but not ``delete_order``) and
``viewer`` (a member of ``Viewers`` only); groups Editors / Finance / Viewers.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Dialog, Page, expect

from tests.e2e.conftest import _spawn_uvicorn, _terminate, csrf_headers
from tests.e2e.test_visual_regression import VIEWPORTS, _capture_or_compare

MATRIX = "/admin/permissions-matrix/"
SAVE = "/admin/permissions-matrix/save"
SIDEBAR_LINK = "sidebar-plugin-permissions-matrix-permissions-matrix"
UNSAVED_NAME = re.compile(r"\(unsaved\)$")


@pytest.fixture
def matrix_base_url(e2e_port: int) -> Iterator[str]:
    """Start the permission-matrix app (:mod:`tests.e2e.apps.permissions_matrix`)."""
    proc, base = _spawn_uvicorn("tests.e2e.apps.permissions_matrix", e2e_port)
    try:
        yield base
    finally:
        _terminate(proc)


def _login(page: Page, base_url: str, username: str = "alice") -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _open_matrix(page: Page, base_url: str, username: str = "alice") -> None:
    _login(page, base_url, username)
    page.goto(base_url + MATRIX)
    expect(page.get_by_role("heading", name="Permission matrix")).to_be_visible()


def _cell(page: Page, model: str, codename: str):
    return page.get_by_test_id(f"pmatrix-cell-{model}-{codename}")


def _unsaved(page: Page):
    return page.get_by_test_id("pmatrix-unsaved-count")


def test_matrix_loads_with_current_grid_for_selected_group(
    page: Page, matrix_base_url: str
) -> None:
    """
    Scenario: matrix loads with current grid for selected group
      Given groups [Editors, Finance, Viewers] and models [Order, Invoice, Product]
      When  alice opens /admin/permissions-matrix/
      Then  Editors is selected and the grid has a row per registered model (3 + the 3 auth models)
      And   each cell is a checkbox named "Editors can <action> <model>" showing the granted value
      And   an action that does not apply prints a dash with its reason for screen readers
      And   the sidebar link to the matrix is the current page
    """
    # Given / When
    _open_matrix(page, matrix_base_url)

    # Then
    expect(page.get_by_test_id("pmatrix-group-select")).to_have_value(re.compile(r"^\d+$"))
    expect(page.get_by_test_id("pmatrix-group-note")).to_have_text(
        "Changes apply to everyone in Editors."
    )
    table = page.get_by_test_id("pmatrix-table")
    expect(table.get_by_role("columnheader")).to_have_text(
        [
            re.compile("Model"),
            re.compile("View"),
            re.compile("Add"),
            re.compile("Change"),
            re.compile("Delete"),
            re.compile("Export"),
            re.compile("Object rules"),
        ]
    )
    expect(table.get_by_role("row")).to_have_count(7)  # header + 3 models + 3 auth models
    # And
    expect(page.get_by_role("checkbox", name="Editors can view orders")).to_be_checked()
    expect(_cell(page, "order", "view_order")).to_be_checked()
    expect(_cell(page, "order", "delete_order")).not_to_be_checked()
    expect(_cell(page, "product", "view_product")).not_to_be_checked()
    # And
    expect(
        page.get_by_role("cell", name=re.compile("Export does not apply to invoices"))
    ).to_have_count(1)
    expect(page.get_by_test_id("pmatrix-cell-invoice-export_invoice")).to_have_count(0)
    # And
    expect(page.get_by_test_id(SIDEBAR_LINK)).to_have_attribute("aria-current", "page")


def test_group_dropdown_swaps_the_grid_without_page_reload(
    page: Page, matrix_base_url: str
) -> None:
    """
    Scenario: group dropdown swaps the grid via HTMX without page reload
      Given the matrix is open for Editors
      When  the user picks Viewers in the Group select
      Then  the grid shows the Viewers permissions and the URL carries the group
      And   the page was not reloaded
    """
    # Given
    _open_matrix(page, matrix_base_url)
    page.evaluate("window.__pmxMarker = 1")
    expect(_cell(page, "order", "change_order")).to_be_checked()

    # When
    page.get_by_test_id("pmatrix-group-select").select_option(label="Viewers")

    # Then
    expect(page.get_by_test_id("pmatrix-group-note")).to_have_text(
        "Changes apply to everyone in Viewers."
    )
    expect(_cell(page, "order", "view_order")).to_be_checked()
    expect(_cell(page, "order", "change_order")).not_to_be_checked()
    expect(page).to_have_url(re.compile(r"/permissions-matrix/\?group_id=\d+$"))
    # And
    assert page.evaluate("window.__pmxMarker") == 1


def test_bulk_save_posts_only_changed_cells(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: bulk save posts only changed cells
      Given the Editors grid is loaded
      When  the user toggles two cells and clicks Save changes
      Then  the POST to /permissions-matrix/save carries exactly those two diff entries
      And   the "Permissions saved" toast names the two changes for Editors
      And   the unsaved count and the dashed marks clear
    """
    # Given
    _open_matrix(page, matrix_base_url)
    expect(_unsaved(page)).to_have_text("0 unsaved changes")

    # When
    _cell(page, "order", "delete_order").check()
    _cell(page, "order", "change_order").uncheck()
    expect(_unsaved(page)).to_have_text("2 unsaved changes")
    expect(page.get_by_role("checkbox", name=UNSAVED_NAME)).to_have_count(2)
    with page.expect_request(lambda r: r.url.endswith(SAVE) and r.method == "POST") as saved:
        page.get_by_test_id("pmatrix-save-btn").click()

    # Then
    body = saved.value.post_data_json
    assert body is not None
    assert {(c["codename"], c["granted"]) for c in body["changes"]} == {
        ("delete_order", True),
        ("change_order", False),
    }
    # And
    toast = page.get_by_test_id("pmatrix-saved-banner")
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("Permissions saved")
    expect(toast).to_contain_text("2 changes for Editors.")
    # And
    expect(_unsaved(page)).to_have_text("0 unsaved changes")
    expect(page.get_by_role("checkbox", name=UNSAVED_NAME)).to_have_count(0)
    page.reload()
    expect(_cell(page, "order", "delete_order")).to_be_checked()
    expect(_cell(page, "order", "change_order")).not_to_be_checked()


def test_conflicting_save_shows_the_conflict_banner_with_reload(
    page: Page, matrix_base_url: str
) -> None:
    """
    Scenario: conflicting save returns 409
      Given the user has the Editors grid loaded with one unsaved change
      And   someone else saved Editors meanwhile (version bumped)
      When  the user clicks Save changes
      Then  a warning banner says "Permissions changed elsewhere" with a Reload link
      And   the change is still on the page, unsaved
      When  the user follows Reload and confirms leaving
      Then  the grid reloads without the change
    """
    # Given
    _open_matrix(page, matrix_base_url)
    _cell(page, "order", "delete_order").check()
    expect(_unsaved(page)).to_have_text("1 unsaved change")
    bumped = page.request.post(f"{matrix_base_url}/_test/bump?group=Editors")
    assert bumped.ok

    # When
    page.get_by_test_id("pmatrix-save-btn").click()

    # Then
    banner = page.get_by_test_id("pmatrix-conflict-banner")
    expect(banner).to_be_visible()
    expect(banner).to_have_attribute("role", "alert")
    expect(banner).to_contain_text("Permissions changed elsewhere.")
    expect(banner).to_contain_text("Nothing was saved; your changes are still on the page.")
    reload = banner.get_by_role("link", name="Reload")
    expect(reload).to_have_attribute("href", re.compile(r"\?group_id=\d+$"))
    # And
    expect(_cell(page, "order", "delete_order")).to_be_checked()
    expect(_unsaved(page)).to_have_text("1 unsaved change")

    # When: leaving with unsaved changes asks first; accept
    page.once("dialog", lambda dialog: dialog.accept())
    reload.click()

    # Then
    expect(page.get_by_test_id("pmatrix-group-note")).to_have_text(
        "Changes apply to everyone in Editors."
    )
    expect(_cell(page, "order", "delete_order")).not_to_be_checked()
    expect(_unsaved(page)).to_have_text("0 unsaved changes")
    expect(page.get_by_test_id("pmatrix-conflict-banner")).to_have_count(0)


def test_rejected_cells_are_marked_and_the_whole_save_is_refused(
    page: Page, matrix_base_url: str
) -> None:
    """
    Scenario: a cell the operator may not grant rejects the whole save
      Given editor (who lacks delete_order) has the Editors grid loaded
      When  editor grants delete_order, revokes view_invoice and clicks Save changes
      Then  a danger alert lists "Delete orders" as not saved
      And   the delete_order cell is marked and describes why
      And   nothing was saved: both changes are still pending and the server state is unchanged
    """
    # Given
    _open_matrix(page, matrix_base_url, username="editor")

    # When
    _cell(page, "order", "delete_order").check()
    _cell(page, "invoice", "view_invoice").uncheck()
    page.get_by_test_id("pmatrix-save-btn").click()

    # Then
    alert = page.get_by_test_id("pmatrix-rejected-banner")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("1 change wasn’t saved.")
    expect(alert).to_contain_text("You can only grant permissions you have yourself:")
    expect(alert.get_by_role("listitem")).to_have_text(["Delete orders"])
    # And
    expect(_cell(page, "order", "delete_order")).to_have_accessible_description(
        "Not saved: you don’t have this permission yourself"
    )
    expect(_cell(page, "invoice", "view_invoice")).to_have_accessible_description("")
    # And
    expect(_unsaved(page)).to_have_text("2 unsaved changes")
    expect(page.get_by_test_id("pmatrix-saved-banner")).to_have_count(0)
    page.once("dialog", lambda dialog: dialog.accept())
    page.reload()
    expect(_cell(page, "order", "delete_order")).not_to_be_checked()
    expect(_cell(page, "invoice", "view_invoice")).to_be_checked()


def test_object_permission_column_opens_an_inline_popover(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: object-permission column opens an inline popover
      Given the Editors group has 2 per-row object permissions on Order
      When  the user clicks the "2 rules" pill on the Order row
      Then  a dialog "Object rules · Editors · Orders" lists the two entries
      And   each entry has a Remove button and the dialog has an "Add rule" affordance
      And   the pill reads expanded
      When  the user presses Escape
      Then  the dialog closes and focus returns to the pill
    """
    # Given
    _open_matrix(page, matrix_base_url)
    pill = page.get_by_test_id("pmatrix-object-cell-order")
    expect(pill).to_have_text(re.compile(r"2 rules"), use_inner_text=True)
    expect(pill).to_have_attribute("aria-expanded", "false")

    # When
    pill.click()

    # Then
    dialog = page.get_by_role("dialog", name=re.compile("Object rules"))
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("heading")).to_have_text(
        re.compile("Object rules · Editors · Orders")
    )
    expect(dialog.get_by_role("listitem")).to_have_count(2)
    # And
    expect(dialog.get_by_role("button", name="Remove rule for 1")).to_be_visible()
    expect(dialog.get_by_role("button", name="Remove rule for 2")).to_be_visible()
    expect(dialog.get_by_role("button", name="Add rule")).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(dialog.get_by_label("Record")).to_be_hidden()
    expect(dialog).to_contain_text("Saved as you go. Group permissions still apply.")
    # And
    expect(pill).to_have_attribute("aria-expanded", "true")

    # When
    page.keyboard.press("Escape")

    # Then
    expect(page.get_by_role("dialog", name=re.compile("Object rules"))).to_have_count(0)
    expect(pill).to_be_focused()
    expect(pill).to_have_attribute("aria-expanded", "false")


def test_object_popover_add_and_remove_update_the_count(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: object rules save on their own and the pill count follows
      Given the Editors group has no object rules on Invoice
      When  the user opens the Invoice pill, clicks Add rule, enters record 7 / Change and adds it
      Then  the popover confirms "Rule for 7 added." and lists the entry
      And   the Invoice pill reads "1 rule" while the matrix still has 0 unsaved changes
      When  the user removes the rule
      Then  the popover confirms the removal with Undo and the pill offers "Add" again
      When  the user clicks Undo
      Then  the rule is back
    """
    # Given
    _open_matrix(page, matrix_base_url)
    pill = page.get_by_test_id("pmatrix-object-cell-invoice")
    expect(pill).to_have_text(re.compile(r"^\s*Add"), use_inner_text=True)

    # When
    pill.click()
    dialog = page.get_by_role("dialog", name=re.compile("Object rules"))
    expect(dialog.get_by_test_id("pmatrix-object-empty")).to_have_text(
        "No object rules. Group permissions apply."
    )
    dialog.get_by_role("button", name="Add rule").click()
    record = dialog.get_by_label("Record")
    expect(record).to_be_focused()
    record.fill("7")
    dialog.get_by_label("Action").select_option(label="Change")
    dialog.get_by_role("button", name="Add", exact=True).click()

    # Then
    dialog = page.get_by_role("dialog", name=re.compile("Object rules"))
    expect(dialog.get_by_role("status")).to_have_text("Rule for 7 added.")
    expect(dialog.get_by_role("listitem")).to_have_count(1)
    expect(dialog.get_by_role("listitem")).to_contain_text("7")
    expect(dialog.get_by_role("listitem")).to_contain_text("Change")
    # And
    expect(pill).to_have_text(re.compile(r"1 rule\b"), use_inner_text=True)
    expect(_unsaved(page)).to_have_text("0 unsaved changes")

    # When
    dialog.get_by_role("button", name="Remove rule for 7").click()

    # Then
    dialog = page.get_by_role("dialog", name=re.compile("Object rules"))
    expect(dialog.get_by_role("status")).to_contain_text("Rule for 7 removed.")
    expect(dialog.get_by_role("listitem")).to_have_count(0)
    expect(pill).to_have_text(re.compile(r"^\s*Add"), use_inner_text=True)

    # When
    dialog.get_by_role("button", name="Undo").click()

    # Then
    dialog = page.get_by_role("dialog", name=re.compile("Object rules"))
    expect(dialog.get_by_role("status")).to_have_text("Rule for 7 added.")
    expect(pill).to_have_text(re.compile(r"1 rule\b"), use_inner_text=True)


def test_per_column_select_all_toggles_every_cell_in_that_column(
    page: Page, matrix_base_url: str
) -> None:
    """
    Scenario: per-column "select all" toggles every cell in that column
      Given Editors may add orders but none of the other five models
      Then  the Add column's select-all is indeterminate
      When  the user ticks it
      Then  every Add cell is checked and five changes are pending
      When  the user unticks it
      Then  no Add cell is checked and one change is pending
    """
    # Given
    _open_matrix(page, matrix_base_url)
    select_all = page.get_by_role("checkbox", name="Editors can add every model")
    expect(select_all).to_have_js_property("indeterminate", True)
    expect(select_all).not_to_be_checked()

    # When
    select_all.click()

    # Then
    for model in ("order", "invoice", "product", "user", "group", "permission"):
        expect(_cell(page, model, f"add_{model}")).to_be_checked()
    expect(select_all).to_have_js_property("indeterminate", False)
    expect(select_all).to_be_checked()
    expect(_unsaved(page)).to_have_text("5 unsaved changes")

    # When
    select_all.click()

    # Then
    for model in ("order", "invoice", "product"):
        expect(_cell(page, model, f"add_{model}")).not_to_be_checked()
    expect(_unsaved(page)).to_have_text("1 unsaved change")
    expect(page.get_by_role("checkbox", name="Editors can add orders (unsaved)")).to_have_count(1)


def test_switching_group_with_unsaved_changes_asks_first(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: switching group with unsaved changes asks first
      Given the Editors grid has one unsaved change
      When  the user picks Viewers and cancels the confirmation
      Then  the Editors grid stays, change included
      When  the user picks Viewers and confirms
      Then  the Viewers grid loads with nothing pending
    """
    # Given
    _open_matrix(page, matrix_base_url)
    select = page.get_by_test_id("pmatrix-group-select")
    editors_id = select.input_value()
    _cell(page, "order", "delete_order").check()

    # When
    dialogs: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", dismiss)
    select.select_option(label="Viewers")

    # Then
    expect(page.get_by_test_id("pmatrix-group-note")).to_have_text(
        "Changes apply to everyone in Editors."
    )
    expect(select).to_have_value(editors_id)
    expect(_cell(page, "order", "delete_order")).to_be_checked()
    expect(_unsaved(page)).to_have_text("1 unsaved change")
    assert dialogs == ["You have unsaved changes. Switch group and lose them?"]

    # When
    page.once("dialog", lambda dialog: dialog.accept())
    select.select_option(label="Viewers")

    # Then
    expect(page.get_by_test_id("pmatrix-group-note")).to_have_text(
        "Changes apply to everyone in Viewers."
    )
    expect(_unsaved(page)).to_have_text("0 unsaved changes")


def test_permission_codename_gates_access_to_the_matrix(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: permission codename gates access to the matrix
      Given viewer lacks "change_groups_permissions"
      When  viewer opens the dashboard and then /admin/permissions-matrix/
      Then  the sidebar has no matrix link and the page answers 403
    """
    # Given
    _login(page, matrix_base_url, username="viewer")

    # When / Then
    expect(page.get_by_test_id("sidebar")).to_be_visible()
    expect(page.get_by_test_id(SIDEBAR_LINK)).to_have_count(0)
    response = page.goto(matrix_base_url + MATRIX)
    assert response is not None
    assert response.status == 403
    expect(page.get_by_test_id("permission-matrix")).to_have_count(0)


def test_order_pages_reflect_a_view_but_not_edit_group(page: Page, matrix_base_url: str) -> None:
    """
    Scenario: detail page reflects a view-but-not-edit role
      Given viewer is a member of Viewers, which holds view_order only
      When  viewer opens the Order list and detail page
      Then  both render, the edit form answers 403
      And   PUT /admin/order/1 returns 403
    """
    # Given
    _login(page, matrix_base_url, username="viewer")

    # When
    page.goto(f"{matrix_base_url}/admin/order")

    # Then
    expect(page.get_by_test_id("row-view-link")).to_have_count(2)
    page.get_by_test_id("row-view-link").first.click()
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    edit_form = page.goto(f"{matrix_base_url}/admin/order/1/edit")
    assert edit_form is not None
    assert edit_form.status == 403
    page.goto(f"{matrix_base_url}/admin/order")
    # And
    response = page.request.put(
        f"{matrix_base_url}/admin/order/1",
        headers=csrf_headers(page),
        form={"title": "edited"},
    )
    assert response.status == 403


@pytest.mark.parametrize("viewport_name", list(VIEWPORTS.keys()))
def test_permission_matrix_visual_baseline(
    page: Page, matrix_base_url: str, viewport_name: str
) -> None:
    """
    Scenario: permission matrix screenshot matches the baseline at {viewport_name}
      Given the viewport is the named breakpoint
      When  the Editors grid loads
      Then  the captured screenshot matches the committed baseline
    """
    # Given
    page.set_viewport_size(VIEWPORTS[viewport_name])

    # When
    _open_matrix(page, matrix_base_url)
    page.wait_for_load_state("networkidle")

    # Then
    _capture_or_compare(page, "permissions", viewport_name)
