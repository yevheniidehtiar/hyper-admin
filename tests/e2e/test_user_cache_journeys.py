"""E2E user journeys with the per-worker user cache on (st-perf-04).

Companion app: :mod:`tests.e2e.apps.user_cache`. It runs with ``user_cache_ttl=5`` (or 0 for the
control runs) and a fake cache clock the tests advance through ``/_test/advance``, so "the TTL
has passed" never sleeps. Writes by "someone else" go through the app's ``/_test/*`` routes:
``via=orm`` and ``via=bulk`` run on this worker (the cache hears about them), ``via=raw`` runs on
a bare connection no session listener sees, standing in for another worker or a CLI.

Selectors follow ``CLAUDE.md``: role, label, text, then test id. No ``ha-*`` classes.
"""

from __future__ import annotations

import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from playwright.sync_api import Browser, Page, expect

if TYPE_CHECKING:
    from collections.abc import Callable

TICKETS = "/admin/ticket"
TTL = 5


@pytest.fixture
def user_cache_base_url(request: pytest.FixtureRequest, start_server: Callable[..., str]) -> str:
    """Start the user-cache app; ``indirect`` parametrization picks the TTL (default 5)."""
    ttl = getattr(request, "param", TTL)
    return start_server("tests.e2e.apps.user_cache", extra_env={"E2E_USER_CACHE_TTL": str(ttl)})


def _login(page: Page, base_url: str, username: str, password: str = "secret123") -> None:  # noqa: S107
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def _sign_in(page: Page, base_url: str, username: str) -> None:
    _login(page, base_url, username)
    expect(page).to_have_url(f"{base_url}/admin/")


def _post(page: Page, base_url: str, path: str, **params: Any) -> None:
    """Call a ``/_test`` route on the host (outside the admin session and CSRF guard)."""
    response = page.request.post(f"{base_url}/_test/{path}", params=params)
    assert response.status == HTTPStatus.OK, response.text()


def _status(page: Page, url: str) -> int:
    """Status of a GET that follows no redirect, reusing the page's cookies."""
    return page.request.get(url, max_redirects=0).status


def _user_selects(page: Page, base_url: str) -> int:
    return int(page.request.get(f"{base_url}/_test/queries").json()["user"])


def _warm(page: Page, base_url: str) -> None:
    """Two requests, so the user is certainly in the cache."""
    for _ in range(2):
        page.goto(base_url + TICKETS)


def _logout(page: Page) -> None:
    page.locator("button[aria-haspopup='true']").click()
    page.get_by_test_id("logout-btn").click()


def _row(page: Page, title: str):
    return page.get_by_test_id("list-row").filter(has_text=title)


@pytest.mark.parametrize("user_cache_base_url", [0, TTL], indirect=True, ids=["ttl0", "ttl5"])
def test_browsing_as_a_staff_user_behaves_the_same_with_the_cache(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: browsing as a cached staff user is identical to TTL 0
      Given staff holds view, add, change and delete on tickets
      When  staff lists, pages, searches, filters and sorts tickets
      Then  every step shows the same result with the cache on as with it off
    """
    base = user_cache_base_url
    # Given staff is signed in
    _sign_in(page, base, "staff")

    # When staff opens the list
    page.goto(base + TICKETS)
    # Then the first page of 45 tickets is shown
    expect(page.get_by_test_id("list-row")).to_have_count(10)
    expect(page.get_by_test_id("pagination-info")).to_contain_text("45")

    # When staff goes to the next page
    page.get_by_test_id("pagination-next").click()
    # Then page 2 is shown
    expect(page.get_by_test_id("pagination-page")).to_contain_text("Page 2")
    expect(page.get_by_test_id("list-row")).to_have_count(10)

    # When staff searches for one ticket
    page.goto(base + TICKETS)
    page.get_by_test_id("search-input").press_sequentially("Ticket 07")
    # Then only that ticket remains
    expect(page.get_by_test_id("list-row")).to_have_count(1)
    expect(_row(page, "Ticket 07")).to_be_visible()

    # When staff filters on one category
    page.goto(base + TICKETS)
    page.get_by_test_id("filter-sidebar").get_by_label("Category").select_option("feature")
    page.get_by_test_id("filter-apply-btn").click()
    expect(page).to_have_url(re.compile(r"filter_category=feature"))
    page.reload()
    # Then only its 15 tickets are listed
    expect(page.get_by_test_id("pagination-info")).to_contain_text("15")

    # When staff sorts by title descending
    page.goto(base + TICKETS)
    header = page.get_by_role("columnheader").filter(has=page.get_by_test_id("sort-title"))
    page.get_by_test_id("sort-title").click()
    expect(header).to_have_attribute("aria-sort", "ascending")
    page.get_by_test_id("sort-title").click()
    expect(header).to_have_attribute("aria-sort", "descending")
    # Then the highest title comes first
    expect(page.get_by_test_id("list-row").first).to_contain_text("Ticket 45")


@pytest.mark.parametrize("user_cache_base_url", [0, TTL], indirect=True, ids=["ttl0", "ttl5"])
def test_maintaining_tickets_as_a_staff_user_behaves_the_same_with_the_cache(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: creating, editing and deleting as a cached staff user is identical to TTL 0
      Given staff holds view, add, change and delete on tickets
      When  staff creates, edits, views, inline-edits and deletes a ticket
      Then  every step shows the same result with the cache on as with it off
    """
    base = user_cache_base_url
    # Given staff is signed in
    _sign_in(page, base, "staff")

    # When staff creates a ticket
    page.goto(base + TICKETS)
    page.get_by_test_id("create-link").click()
    page.get_by_label("Title").fill("Brand new ticket")
    page.get_by_role("button", name="Create", exact=True).click()
    # Then its detail page opens
    expect(page).to_have_url(re.compile(rf"{TICKETS}/\d+$"))
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Brand new ticket")
    pk = page.url.rstrip("/").rsplit("/", 1)[-1]

    # When staff edits it
    page.get_by_test_id("detail-edit-link").click()
    page.get_by_label("Title").fill("Renamed ticket")
    page.get_by_role("button", name="Update").click()
    expect(page).not_to_have_url(re.compile(r"/edit$"))
    # Then the detail page shows the new title and still offers Edit and Delete
    page.goto(f"{base}{TICKETS}/{pk}")
    expect(page.get_by_test_id("detail-fields")).to_contain_text("Renamed ticket")
    expect(page.get_by_test_id("detail-delete-btn")).to_be_visible()

    # When staff changes the status inline from the list
    page.goto(base + TICKETS)
    page.get_by_test_id("search-input").press_sequentially("Renamed")
    page.get_by_test_id(f"cell-edit-status-{pk}").click()
    page.get_by_test_id(f"cell-editor-status-{pk}").get_by_role("textbox").fill("closed")
    page.get_by_test_id(f"cell-save-status-{pk}").click()
    # Then the cell shows the new value
    expect(page.get_by_test_id(f"cell-value-status-{pk}")).to_contain_text("closed")

    # When staff deletes it from the list
    row = _row(page, "Renamed ticket")
    row.get_by_test_id("row-delete-btn").click()
    page.get_by_test_id("dialog-confirm-delete").get_by_role("button", name="Delete").click()
    # Then it is gone
    expect(_row(page, "Renamed ticket")).to_have_count(0)
    assert _status(page, f"{base}{TICKETS}/{pk}") == HTTPStatus.NOT_FOUND


def _status_of(page: Page, url: str) -> int:
    """Status of a browser navigation to ``url``."""
    response = page.goto(url)
    assert response is not None
    return response.status


# -- same-worker writes show up immediately ---------------------------------------------------


@pytest.mark.parametrize("via", ["orm", "bulk"])
def test_revoked_permission_blocks_the_next_request(
    page: Page, user_cache_base_url: str, via: str
) -> None:
    """
    Scenario: a revoked permission blocks the very next request
      Given staff has a warm cache entry and can list tickets
      When  view_ticket is revoked on this worker (ORM delete or bulk DELETE)
      Then  the next list request answers 403, without waiting for the TTL
    """
    base = user_cache_base_url
    # Given staff has a warm cache entry and can list tickets
    _sign_in(page, base, "staff")
    _warm(page, base)
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK

    # When view_ticket is revoked on this worker
    _post(page, base, "revoke", user="staff", codename="view_ticket", via=via)

    # Then the next list request answers 403
    assert _status_of(page, base + TICKETS) == HTTPStatus.FORBIDDEN


def test_leaving_a_group_blocks_the_next_request(page: Page, user_cache_base_url: str) -> None:
    """
    Scenario: removing a user from a group takes the group's permissions away at once
      Given grouped gets view_ticket from the Support group and has a warm cache entry
      When  grouped is removed from the group on this worker
      Then  the next list request answers 403
    """
    base = user_cache_base_url
    # Given grouped gets view_ticket from the Support group and has a warm cache entry
    _sign_in(page, base, "grouped")
    _warm(page, base)
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK

    # When grouped is removed from the group
    _post(page, base, "leave_group", user="grouped")

    # Then the next list request answers 403
    assert _status_of(page, base + TICKETS) == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize("via", ["orm", "bulk"])
def test_deactivated_user_is_sent_to_login_at_once(
    page: Page, user_cache_base_url: str, via: str
) -> None:
    """
    Scenario: a deactivated user is sent to login on the next request
      Given temp is signed in with a warm cache entry
      When  temp is deactivated on this worker
      Then  the next admin request redirects to the login page
    """
    base = user_cache_base_url
    # Given temp is signed in with a warm cache entry
    _sign_in(page, base, "temp")
    _warm(page, base)

    # When temp is deactivated
    _post(page, base, "set", user="temp", field="is_active", value=0, via=via)

    # Then the next admin request redirects to the login page
    page.goto(base + TICKETS)
    expect(page).to_have_url(f"{base}/admin/login")
    expect(page.get_by_role("button", name="Sign in")).to_be_visible()


def test_password_change_reaches_the_next_login(page: Page, user_cache_base_url: str) -> None:
    """
    Scenario: a changed password applies to the next sign-in
      Given pwuser is signed in with a warm cache entry
      When  the password is changed on this worker
      Then  the open session keeps working and, after logout, only the new password signs in
    """
    base = user_cache_base_url
    # Given pwuser is signed in with a warm cache entry
    _sign_in(page, base, "pwuser")
    _warm(page, base)

    # When the password is changed
    _post(page, base, "password", user="pwuser", password="brand-new-pw")

    # Then the open session keeps working
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK
    # And after logout the old password is refused
    _logout(page)
    _login(page, base, "pwuser")
    expect(page.get_by_text("Invalid username or password.")).to_be_visible()
    # And the new one signs in
    _login(page, base, "pwuser", password="brand-new-pw")
    expect(page).to_have_url(f"{base}/admin/")


@pytest.mark.parametrize("via", ["orm", "bulk"])
def test_dropping_the_superuser_flag_applies_to_the_next_request(
    page: Page, user_cache_base_url: str, via: str
) -> None:
    """
    Scenario: a user who stops being a superuser loses access at once
      Given boss is a superuser without grants and has a warm cache entry
      When  the superuser flag is removed on this worker
      Then  the next list request answers 403
    """
    base = user_cache_base_url
    # Given boss is a superuser without grants and has a warm cache entry
    _sign_in(page, base, "boss")
    _warm(page, base)
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK

    # When the superuser flag is removed
    _post(page, base, "set", user="boss", field="is_superuser", value=0, via=via)

    # Then the next list request answers 403
    assert _status_of(page, base + TICKETS) == HTTPStatus.FORBIDDEN


# -- writes from another worker are bounded by the TTL ----------------------------------------


def test_deactivation_on_another_worker_lands_after_the_ttl(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: a deactivation made elsewhere takes effect once the TTL passes
      Given temp has a warm cache entry (TTL 5)
      When  temp is deactivated by a write no session listener sees
      Then  requests inside the TTL still succeed
      And   the first request after the TTL redirects to login
    """
    base = user_cache_base_url
    # Given temp has a warm cache entry
    _sign_in(page, base, "temp")
    _warm(page, base)

    # When temp is deactivated by a write no session listener sees
    _post(page, base, "set", user="temp", field="is_active", value=0, via="raw")

    # Then requests inside the TTL still succeed
    _post(page, base, "advance", seconds=4)
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK
    # And the first request after the TTL redirects to login
    _post(page, base, "advance", seconds=2)
    page.goto(base + TICKETS)
    expect(page).to_have_url(f"{base}/admin/login")


def test_superuser_flag_dropped_on_another_worker_lands_after_the_ttl(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: a dropped superuser flag made elsewhere takes effect once the TTL passes
      Given boss has a warm cache entry (TTL 5)
      When  the flag is removed by a write no session listener sees
      Then  requests inside the TTL still succeed
      And   the first request after the TTL answers 403
    """
    base = user_cache_base_url
    # Given boss has a warm cache entry
    _sign_in(page, base, "boss")
    _warm(page, base)

    # When the flag is removed by a write no session listener sees
    _post(page, base, "set", user="boss", field="is_superuser", value=0, via="raw")

    # Then requests inside the TTL still succeed
    _post(page, base, "advance", seconds=4)
    assert _status_of(page, base + TICKETS) == HTTPStatus.OK
    # And the first request after the TTL answers 403
    _post(page, base, "advance", seconds=2)
    assert _status_of(page, base + TICKETS) == HTTPStatus.FORBIDDEN


def test_permission_revoked_on_another_worker_leaves_the_menu_after_the_ttl(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: a permission revoked elsewhere is enforced at once but leaves the menu after the TTL
      Given staff has a warm cache entry and sees Tickets in the sidebar
      When  view_ticket is revoked by a write no session listener sees
      Then  the list answers 403 immediately (the gate reads the database)
      And   the sidebar keeps Tickets inside the TTL and drops it after
    """
    base = user_cache_base_url
    # Given staff has a warm cache entry and sees Tickets in the sidebar
    _sign_in(page, base, "staff")
    _warm(page, base)
    page.goto(f"{base}/admin/")
    expect(page.get_by_test_id("nav-ticket")).to_be_visible()

    # When view_ticket is revoked by a write no session listener sees
    _post(page, base, "revoke", user="staff", codename="view_ticket", via="raw")

    # Then the list answers 403 immediately
    assert _status_of(page, base + TICKETS) == HTTPStatus.FORBIDDEN
    # And the sidebar keeps Tickets inside the TTL
    _post(page, base, "advance", seconds=4)
    page.goto(f"{base}/admin/")
    expect(page.get_by_test_id("nav-ticket")).to_be_visible()
    # And drops it after the TTL
    _post(page, base, "advance", seconds=2)
    page.goto(f"{base}/admin/")
    expect(page.get_by_test_id("nav-ticket")).to_have_count(0)


# -- isolation between users ------------------------------------------------------------------


def test_two_users_alternating_never_see_each_others_access(
    page: Page, browser: Browser, user_cache_base_url: str
) -> None:
    """
    Scenario: two cached users alternating never leak into each other
      Given staff (full access) and viewer (read only) are signed in from two browsers
      When  they alternate list and create requests several times
      Then  staff always has Delete and can open Create, viewer has neither, and each is greeted by name
    """
    base = user_cache_base_url
    # Given staff and viewer are signed in from two browsers
    _sign_in(page, base, "staff")
    viewer = browser.new_context().new_page()
    _sign_in(viewer, base, "viewer")

    # When they alternate list and create requests
    for _ in range(3):
        # Then staff has Delete, can open Create and is greeted by name
        page.goto(base + TICKETS)
        expect(page.get_by_test_id("row-delete-btn").first).to_be_visible()
        expect(page.get_by_test_id("current-user")).to_contain_text("staff")
        assert _status_of(page, f"{base}{TICKETS}/create") == HTTPStatus.OK

        # And viewer has neither and cannot open the create form
        viewer.goto(base + TICKETS)
        expect(viewer.get_by_test_id("list-table")).to_be_visible()
        expect(viewer.get_by_test_id("row-delete-btn")).to_have_count(0)
        expect(viewer.get_by_test_id("current-user")).to_contain_text("viewer")
        assert _status_of(viewer, f"{base}{TICKETS}/create") == HTTPStatus.FORBIDDEN


def test_logging_in_as_another_user_after_logout_gets_that_user(
    page: Page, user_cache_base_url: str
) -> None:
    """
    Scenario: logout then login as someone else yields the new identity, not the cached one
      Given staff has a warm cache entry in this browser
      When  staff logs out and viewer logs in from the same browser
      Then  the pages show viewer with read-only access
      And   after logout the admin is closed again
    """
    base = user_cache_base_url
    # Given staff has a warm cache entry in this browser
    _sign_in(page, base, "staff")
    _warm(page, base)
    expect(page.get_by_test_id("row-delete-btn").first).to_be_visible()

    # When staff logs out and viewer logs in from the same browser
    _logout(page)
    expect(page).to_have_url(f"{base}/admin/login")
    _sign_in(page, base, "viewer")

    # Then the pages show viewer with read-only access
    page.goto(base + TICKETS)
    expect(page.get_by_test_id("current-user")).to_contain_text("viewer")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    expect(page.get_by_test_id("row-delete-btn")).to_have_count(0)
    assert _status_of(page, f"{base}{TICKETS}/create") == HTTPStatus.FORBIDDEN
    # And after logout the admin is closed again
    page.goto(base + TICKETS)
    _logout(page)
    page.goto(base + TICKETS)
    expect(page).to_have_url(f"{base}/admin/login")


# -- query count ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user_cache_base_url", "cached"), [(0, False), (TTL, True)], indirect=["user_cache_base_url"]
)
def test_repeated_pages_run_the_user_query_once_per_ttl_window(
    page: Page, user_cache_base_url: str, cached: bool
) -> None:
    """
    Scenario: repeated list, search and edit loads run the user query once per TTL window
      Given staff is signed in
      When  staff loads the list, a search and an edit form several times
      Then  with TTL 5 the user table is not queried again inside the TTL, and exactly once
            after it; with TTL 0 every request queries it
    """
    base = user_cache_base_url
    pages = [
        TICKETS,
        f"{TICKETS}?search=Ticket 07",
        f"{TICKETS}/1/edit",
        TICKETS,
        f"{TICKETS}/1/edit",
    ]
    # Given staff is signed in
    _sign_in(page, base, "staff")

    # When staff loads the pages inside the TTL window
    _post(page, base, "reset")
    for path in pages:
        page.goto(base + path)
    inside = _user_selects(page, base)

    # Then the user table is not queried again with the cache, and every time without
    if cached:
        assert inside == 0
    else:
        assert inside >= len(pages)

    # When the TTL has passed and staff loads the pages again
    _post(page, base, "advance", seconds=TTL + 1)
    _post(page, base, "reset")
    for path in pages:
        page.goto(base + path)
    after = _user_selects(page, base)

    # Then the user is loaded exactly once with the cache
    if cached:
        assert after == 1
    else:
        assert after >= len(pages)
