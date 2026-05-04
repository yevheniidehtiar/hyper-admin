"""End-to-end tests for object-level permissions and row-level security (C3-B, #482).

Spec: ``docs/specs/object-permissions-mfa.md`` — Track A (integration scenarios).

Each test maps 1:1 to an SDD Track A integration scenario. Inline
``# Given / # When / # Then`` comments are mandatory (BDD conventions).

Selectors follow ``CLAUDE.md`` (E2E Selector Convention):
``get_by_role`` > ``get_by_label`` > ``get_by_text`` > ``get_by_test_id``.
``ha-*`` CSS classes are styling-only and never used as selectors.

The companion app (``tests.e2e._object_perm_app``) registers two test models
that isolate each enforcement layer:

* ``Order`` — protected ONLY by an :class:`ObjectPermissionChecker` that
  denies non-superusers any interaction with id 40. Verifies the four
  detail/update/delete/superuser-bypass scenarios.
* ``Document`` — protected ONLY by ``ModelAdmin.get_queryset`` filtering
  rows to ``request.state.user.id``. Verifies the RLS list scenario.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str, username: str, password: str = "secret123") -> None:  # noqa: S107
    """Submit the admin login form and wait until we reach the dashboard."""
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def test_staff_cannot_view_another_users_record_when_object_permission_denies(
    page: Page, object_perm_base_url: str
) -> None:
    """
    Scenario: staff cannot view another user's record when object permission denies
      Given user "bob" has view_order model permission
      And   ObjectPermissionChecker denies "bob" access to order#40
      When  GET /admin/order/40
      Then  the response is 403 Forbidden
    """
    # Given bob is logged in (he holds view_order; the model-level layer permits)
    _login(page, object_perm_base_url, "bob")

    # When bob navigates directly to order #40
    response = page.request.get(f"{object_perm_base_url}/admin/order/40")

    # Then the object-level checker denies — 403, not 200
    assert response.status == 403


def test_object_permission_check_is_enforced_on_update(
    page: Page, object_perm_base_url: str
) -> None:
    """
    Scenario: object permission check is enforced on update
      Given ObjectPermissionChecker denies "bob" change access to order#40
      When  PUT /admin/order/40 with valid data (the wired update method)
      Then  the response is 403 Forbidden
    """
    # Given bob is logged in (he holds change_order at the model level)
    _login(page, object_perm_base_url, "bob")

    # When bob attempts to update order #40
    response = page.request.put(
        f"{object_perm_base_url}/admin/order/40",
        form={"title": "hacked", "owner_id": "99"},
        headers={"HX-Request": "true"},
    )

    # Then the object-level checker blocks the change — 403
    assert response.status == 403


def test_object_permission_check_is_enforced_on_delete(
    page: Page, object_perm_base_url: str
) -> None:
    """
    Scenario: object permission check is enforced on delete
      Given ObjectPermissionChecker denies "bob" delete access to order#40
      When  DELETE /admin/order/40 (the wired delete method)
      Then  the response is 403 Forbidden
    """
    # Given bob is logged in (he holds delete_order at the model level)
    _login(page, object_perm_base_url, "bob")

    # When bob attempts to delete order #40
    response = page.request.delete(
        f"{object_perm_base_url}/admin/order/40",
        headers={"HX-Request": "true"},
    )

    # Then the object-level checker blocks the delete — 403
    assert response.status == 403


def test_superuser_bypasses_object_level_checks(page: Page, object_perm_base_url: str) -> None:
    """
    Scenario: superuser bypasses object-level checks
      Given a superuser "admin"
      And   ObjectPermissionChecker would deny order#40 for everyone non-super
      When  GET /admin/order/40
      Then  the response is 200 OK
    """
    # Given the superuser is logged in
    _login(page, object_perm_base_url, "admin")

    # When the superuser navigates to order #40
    page.goto(f"{object_perm_base_url}/admin/order/40")

    # Then the page renders normally — the checker's superuser branch wins
    expect(page.get_by_test_id("detail-fields")).to_be_visible()
    expect(page.get_by_role("heading", name="alice-order-A")).to_be_visible()


def test_get_queryset_filters_list_results_visible_to_non_superuser(
    page: Page, object_perm_base_url: str
) -> None:
    """
    Scenario: get_queryset filters list results visible to non-superuser
      Given a non-superuser whose ModelAdmin.get_queryset returns {"owner_id": user.id}
      When  GET /admin/document/
      Then  only their owner_id rows are visible in the list table
      And   the count reflects the filtered total
    """
    # Given bob is logged in and three documents exist (two owned by bob, one not)
    _login(page, object_perm_base_url, "bob")

    # When bob visits the Document list
    page.goto(f"{object_perm_base_url}/admin/document")

    # Then only his rows appear in the list table
    table = page.get_by_test_id("list-table")
    expect(table).to_be_visible()
    expect(table.get_by_text("bob-doc-A")).to_be_visible()
    expect(table.get_by_text("bob-doc-B")).to_be_visible()
    # And alice's row is filtered out
    expect(table.get_by_text("alice-doc-A")).to_have_count(0)
    # And the row count reflects the filtered total (2 of 3)
    rows = page.get_by_test_id("list-row")
    expect(rows).to_have_count(2)
    # And the pagination total reflects the filtered count (not the unscoped 3)
    expect(page.get_by_test_id("pagination-info")).to_contain_text("of 2 results")
