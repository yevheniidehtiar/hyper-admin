"""E2E coverage for live CRUD notifications across two browser sessions (story #313).

Spec: ``docs/specs/realtime-crud-notifications.md`` -- one test per browser-observable BDD
scenario, named after it. The companion app (``tests.e2e.apps.realtime_notifications``) seeds
``alice`` (id 1) and ``bob`` (id 2) as superusers and ``carol`` (id 3) without any permission,
all with password ``secret123``; 42 Articles (odd ids ``published``, even ids ``draft``,
titles ``Article 01``..``Article 42``), 3 Comments and 3 Notes per superuser. ``NoteAdmin``
scopes rows to the signed-in user through ``get_queryset``.

Scenarios not covered here because they are pure unit concerns (no browser-observable
outcome): "a noisy model can opt out" (nothing published on the AuditLog channel) and
"publish failure never fails the request". "Nothing is published on the Comment channel" is
checked through a hand-made subscription that must receive no frame.

DOM contract the client implements: the list root ``#model-list`` carries
``data-realtime-model``; rows carry ``data-pk``; toasts are ``data-testid="realtime-toast"``
(``role=status``); a changed row gets ``data-realtime-flash="true"``; the navbar status
element carries ``data-realtime-self``.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from playwright.sync_api import Browser, BrowserContext, ConsoleMessage, Page, expect

from tests.e2e.conftest import csrf_headers

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

APP = "tests.e2e.apps.realtime_notifications"
ARTICLES = "/admin/article"
HOOK = "realtime-hook"
NEWEST_FIRST = f"{ARTICLES}?sort_by=id&sort_direction=desc"
# Debounce (300 ms) + request + swap, with slack for a loaded CI box.
LIVE_MS = 8_000
# How long to watch for something that must NOT happen.
QUIET_MS = 1_500

# Records every frame the page's sockets send, so tests can assert on subscribe frames.
RECORD_SENT_JS = """
(() => {
  window.__sent = [];
  const send = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) {
    window.__sent.push(String(data));
    return send.call(this, data);
  };
})();
"""

# A hand-made socket (a forged client) that subscribes to a model and collects server frames.
FORGE_JS = """
async ([model, url]) => {
  window.__forged = [];
  const ws = new WebSocket(url);
  ws.onmessage = (e) => window.__forged.push(String(e.data));
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = () => reject(new Error("websocket failed"));
  });
  ws.send(JSON.stringify({type: "subscribe", model}));
  window.__forgedSocket = ws;
}
"""


@pytest.fixture
def notif_url(start_server: Callable[..., str]) -> str:
    """Realtime app with notifications on for every model."""
    return start_server(APP)


@pytest.fixture
def optin_url(start_server: Callable[..., str]) -> str:
    """``notifications=False``; only ``ArticleAdmin`` opts in."""
    return start_server(APP, extra_env={"RT_MODE": "optin"})


@pytest.fixture
def off_url(start_server: Callable[..., str]) -> str:
    """``Admin(realtime=None)``."""
    return start_server(APP, extra_env={"RT_MODE": "off"})


def _login(page: Page, base_url: str, username: str) -> None:
    page.goto(f"{base_url}/admin/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill("secret123")
    page.get_by_role("button", name="Sign in").click()
    expect(page).to_have_url(f"{base_url}/admin/")


def _record_error(errors: list[str], msg: ConsoleMessage) -> None:
    # Browsers probe /favicon.ico on their own; the app serves none. The 403 console line
    # is the browser echoing a deliberately forbidden page load.
    if msg.type != "error" or msg.location["url"].endswith("favicon.ico"):
        return
    if "403" in msg.text and "Forbidden" in msg.text:
        return
    errors.append(f"{msg.text} ({msg.location['url']})")


def _watch(context: BrowserContext, errors: list[str]) -> None:
    def attach(page: Page) -> None:
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: _record_error(errors, msg))

    for page in context.pages:
        attach(page)
    context.on("page", attach)


@contextmanager
def _sessions(
    browser: Browser, base_url: str, *usernames: str
) -> Iterator[tuple[list[BrowserContext], list[str]]]:
    """One signed-in browser context per user, sharing one list of console errors."""
    contexts = [browser.new_context() for _ in usernames]
    errors: list[str] = []
    try:
        for context, username in zip(contexts, usernames, strict=True):
            context.add_init_script(RECORD_SENT_JS)
            _login(context.new_page(), base_url, username)
            _watch(context, errors)
        yield contexts, errors
    finally:
        for context in contexts:
            context.close()


def _open_list(context: BrowserContext, base_url: str, path: str = ARTICLES) -> Page:
    page = context.new_page()
    page.goto(f"{base_url}{path}")
    expect(page.get_by_test_id("list-table")).to_be_visible()
    return page


def _row(page: Page, pk: int | str) -> Any:
    return page.get_by_test_id("list-row").and_(page.locator(f'[data-pk="{pk}"]'))


def _total(page: Page) -> Any:
    return page.get_by_test_id("pagination-info")


def _toast(page: Page) -> Any:
    return page.get_by_test_id("realtime-toast")


def _create(context: BrowserContext, base_url: str, path: str, **fields: str) -> str:
    """Fill and submit the create form in a fresh tab; return the new record's pk."""
    page = context.new_page()
    page.goto(f"{base_url}{path}/create")
    for label, value in fields.items():
        page.get_by_label(label).fill(value)
    page.get_by_role("button", name="Create").click()
    expect(page).to_have_url(re.compile(rf"{re.escape(path)}/\d+$"))
    pk = page.url.rsplit("/", 1)[1]
    page.close()
    return pk


def _hx_list_requests(page: Page, path: str = ARTICLES) -> list[str]:
    """Collect the HTMX list re-fetch URLs the page sends from now on."""
    seen: list[str] = []

    def on_request(request: Any) -> None:
        url = request.url.split("?", 1)[0]
        if url.endswith(path) and request.headers.get("hx-request"):
            seen.append(request.url)

    page.on("request", on_request)
    return seen


def _forge(page: Page, base_url: str, model: str) -> None:
    """Open a raw socket on ``page`` and subscribe it to ``model``'s CRUD channel."""
    ws_url = base_url.replace("http", "ws", 1) + "/admin/realtime/ws"
    page.evaluate(FORGE_JS, [model, ws_url])


def _forged_frames(page: Page) -> list[dict[str, Any]]:
    """JSON frames the forged socket received; the plain-text heartbeat is not a frame."""
    return [json.loads(raw) for raw in page.evaluate("window.__forged") if raw.startswith("{")]


def _sent_subscribes(page: Page) -> list[str]:
    sent = [json.loads(raw) for raw in page.evaluate("window.__sent || []")]
    return [frame["model"] for frame in sent if frame.get("type") == "subscribe"]


def test_create_by_another_user_refreshes_the_list_and_shows_a_toast(
    browser: Browser, notif_url: str
) -> None:
    """
    Scenario: create by another user refreshes the list and shows a toast
      Given users A and B both have the Article list open with realtime enabled
      When  A creates an Article
      Then  B's list shows the new row without a page reload
      And   B sees a toast "A created Article #<pk>"
      And   A sees no toast for their own change
    """
    # Given alice (A) and bob (B) both have the Article list open
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        # (newest first: the new row lands on page 1 of the default 10-row page size)
        alice_list = _open_list(alice, notif_url, NEWEST_FIRST)
        bob_list = _open_list(bob, notif_url, NEWEST_FIRST)
        expect(bob_list.get_by_test_id(HOOK)).to_have_count(1)
        expect(alice_list.get_by_test_id("realtime-status")).to_have_attribute(
            "data-realtime-self", "1"
        )
        marker = "no-reload-marker"
        bob_list.evaluate(f"window.name = '{marker}'; window.__noReload = true")

        # When alice creates an Article
        pk = _create(alice, notif_url, ARTICLES, Title="Fresh from alice")

        # Then bob's list shows the new row without a page reload
        expect(_row(bob_list, pk)).to_contain_text("Fresh from alice", timeout=LIVE_MS)
        assert bob_list.evaluate("window.__noReload") is True
        # And bob sees the toast naming alice and the record
        expect(_toast(bob_list)).to_have_text(f"alice created Article #{pk}")
        expect(_toast(bob_list)).to_have_attribute("role", "status")
        # And alice's own list refreshed but she gets no toast for her own change
        expect(_row(alice_list, pk)).to_be_visible(timeout=LIVE_MS)
        expect(_toast(alice_list)).to_have_count(0)
        assert errors == []


def test_delete_by_another_user_removes_the_row(browser: Browser, notif_url: str) -> None:
    """
    Scenario: delete by another user removes the row
      Given users A and B both have the Article list open
      When  A deletes an Article that B can see
      Then  the row disappears from B's list without a reload
      And   B's pagination total drops by one
    """
    # Given both lists are open and bob sees Article 5 (42 results)
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        alice_list = _open_list(alice, notif_url)
        bob_list = _open_list(bob, notif_url)
        expect(_row(bob_list, 5)).to_be_visible()
        expect(_total(bob_list)).to_contain_text("of 42 results")

        # When alice deletes Article 5
        alice_list.on("dialog", lambda dialog: dialog.accept())
        _row(alice_list, 5).get_by_test_id("row-delete-btn").click()

        # Then the row disappears from bob's list and the total drops by one
        expect(_row(bob_list, 5)).to_have_count(0, timeout=LIVE_MS)
        expect(_total(bob_list)).to_contain_text("of 41 results")
        assert errors == []


def test_create_by_another_user_updates_the_total_counter(browser: Browser, notif_url: str) -> None:
    """
    Scenario: create by another user updates the total counter
      Given B's Article list shows "Showing 1 to 10 of 42 results"
      When  A creates an Article
      Then  B's list shows "of 43 results" without a reload
    """
    # Given bob's list shows "Showing 1 to 10 of 42 results"
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, notif_url)
        expect(_total(bob_list)).to_contain_text("Showing 1 to 10 of 42 results")

        # When alice creates an Article
        _create(alice, notif_url, ARTICLES, Title="One more")

        # Then the counter reads 43 without a reload
        expect(_total(bob_list)).to_contain_text("of 43 results", timeout=LIVE_MS)
        assert errors == []


def test_update_by_another_user_refreshes_and_highlights_the_row(
    browser: Browser, notif_url: str
) -> None:
    """
    Scenario: update by another user refreshes and highlights the row
      Given users A and B both have the Article list open
      When  A edits an Article's title
      Then  B's list shows the new title without a reload
      And   the changed row is briefly highlighted
      And   B sees no toast
    """
    # Given both lists are open
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, notif_url)
        expect(_row(bob_list, 3)).to_contain_text("Article 03")

        # When alice edits Article 3's title
        form = alice.new_page()
        form.goto(f"{notif_url}{ARTICLES}/3/edit")
        form.get_by_label("Title").fill("Article 03 retitled")
        form.get_by_role("button", name="Update").click()

        # Then bob's list shows the new title and flashes that row
        row = _row(bob_list, 3)
        expect(row).to_contain_text("Article 03 retitled", timeout=LIVE_MS)
        expect(row).to_have_attribute("data-realtime-flash", "true")
        # And bob sees no toast for an update
        expect(_toast(bob_list)).to_have_count(0)
        assert errors == []


def test_delete_by_another_user_shows_a_toast(browser: Browser, notif_url: str) -> None:
    """
    Scenario: delete by another user shows a toast
      Given users A and B both have the Article list open
      When  A deletes an Article
      Then  B sees a toast "A deleted Article #<pk>"
    """
    # Given both lists are open
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        alice_list = _open_list(alice, notif_url)
        bob_list = _open_list(bob, notif_url)

        # When alice deletes Article 7
        alice_list.on("dialog", lambda dialog: dialog.accept())
        _row(alice_list, 7).get_by_test_id("row-delete-btn").click()

        # Then bob sees the toast
        expect(_toast(bob_list)).to_have_text("alice deleted Article #7", timeout=LIVE_MS)
        assert errors == []


def test_bursts_collapse_into_one_toast(browser: Browser, notif_url: str) -> None:
    """
    Scenario: bursts collapse into one toast
      Given users A and B both have the Article list open
      When  A bulk-deletes 12 Articles
      Then  B's list re-fetches once
      And   B sees a single toast "A changed 12 Articles"
    """
    # Given both lists are open
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        alice_list = _open_list(alice, notif_url)
        bob_list = _open_list(bob, notif_url)
        refetches = _hx_list_requests(bob_list)
        headers = csrf_headers(alice_list)

        # When alice deletes 12 Articles in one burst (Article 21..32)
        alice_list.evaluate(
            """async ([headers, base]) => {
              await Promise.all(Array.from({length: 12}, (_, i) =>
                fetch(`${base}/${21 + i}`, {method: "DELETE", headers})));
            }""",
            [headers, f"{notif_url}{ARTICLES}"],
        )

        # Then bob sees one summary toast
        expect(_toast(bob_list)).to_have_text("alice changed 12 Articles", timeout=LIVE_MS)
        expect(_toast(bob_list)).to_have_count(1)
        expect(_total(bob_list)).to_contain_text("of 30 results")
        # And his list re-fetched once
        bob_list.wait_for_timeout(QUIET_MS)
        assert len(refetches) == 1, refetches
        assert errors == []


def test_hidden_tab_defers_the_refresh(browser: Browser, notif_url: str) -> None:
    """
    Scenario: hidden tab defers the refresh
      Given B's Article list is open in a background tab
      When  A creates an Article
      Then  B's tab sends no list request while hidden
      When  B switches back to the tab
      Then  the list re-fetches once and shows the new row
    """
    # Given bob's list is open and the tab reports itself hidden
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, notif_url, NEWEST_FIRST)
        bob_list.evaluate(
            """() => {
              Object.defineProperty(document, "visibilityState",
                {configurable: true, get: () => "hidden"});
              Object.defineProperty(document, "hidden", {configurable: true, get: () => true});
              document.dispatchEvent(new Event("visibilitychange"));
            }"""
        )
        refetches = _hx_list_requests(bob_list)

        # When alice creates an Article
        pk = _create(alice, notif_url, ARTICLES, Title="While you were away")

        # Then bob's hidden tab sends no list request
        bob_list.wait_for_timeout(QUIET_MS)
        assert refetches == []
        expect(_row(bob_list, pk)).to_have_count(0)

        # When bob switches back to the tab
        bob_list.evaluate(
            """() => {
              Object.defineProperty(document, "visibilityState",
                {configurable: true, get: () => "visible"});
              Object.defineProperty(document, "hidden", {configurable: true, get: () => false});
              document.dispatchEvent(new Event("visibilitychange"));
            }"""
        )

        # Then the list re-fetches once and shows the new row
        expect(_row(bob_list, pk)).to_contain_text("While you were away", timeout=LIVE_MS)
        bob_list.wait_for_timeout(QUIET_MS)
        assert len(refetches) == 1, refetches
        assert errors == []


def test_only_selected_models_notify(browser: Browser, optin_url: str) -> None:
    """
    Scenario: only selected models notify
      Given RealtimeSettings(notifications=False)
      And   ArticleAdmin sets realtime_notifications=True
      When  A creates an Article and a Comment
      Then  B's Article list refreshes live
      And   B's Comment list renders no subscription hook and does not change until reloaded
      And   nothing is published on the Comment channel
    """
    # Given only ArticleAdmin opted in; bob has both lists open
    with _sessions(browser, optin_url, "alice", "bob") as ((alice, bob), errors):
        article_list = _open_list(bob, optin_url, NEWEST_FIRST)
        comment_list = _open_list(bob, optin_url, "/admin/comment")
        expect(article_list.get_by_test_id(HOOK)).to_have_count(1)
        # And a hand-made subscription to the Comment channel stays silent
        _forge(comment_list, optin_url, "comment")

        # When alice creates an Article and a Comment
        article_pk = _create(alice, optin_url, ARTICLES, Title="Opted in")
        _create(alice, optin_url, "/admin/comment", Body="Not announced")

        # Then the Article list refreshes live
        expect(_row(article_list, article_pk)).to_contain_text("Opted in", timeout=LIVE_MS)
        # And the Comment list has no hook and does not change
        expect(comment_list.get_by_test_id(HOOK)).to_have_count(0)
        comment_list.wait_for_timeout(QUIET_MS)
        expect(comment_list.get_by_text("Not announced")).to_have_count(0)
        # And nothing was published on the Comment channel
        assert _forged_frames(comment_list) == []
        assert errors == []


def test_b_s_list_keeps_its_own_view_state(browser: Browser, notif_url: str) -> None:
    """
    Scenario: B's list keeps its own view state
      Given B's Article list is on page 2, filtered by status=draft, sorted by title
      When  A creates an Article
      Then  B's refreshed list is still page 2, status=draft, sorted by title
      And   B's pagination total counts only the rows matching status=draft
    """
    # Given bob is on page 2 of the draft articles sorted by title (21 drafts)
    view = "?page=2&filter_status=draft&sort_by=title&sort_direction=asc"
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, notif_url, ARTICLES + view)
        expect(_total(bob_list)).to_contain_text("Showing 11 to 20 of 21 results")
        url_before = bob_list.url

        # When alice creates a draft Article
        _create(alice, notif_url, ARTICLES, Title="Zulu draft", Status="draft")

        # Then bob's refreshed list keeps page, filter and sort, and counts only drafts
        expect(_total(bob_list)).to_contain_text("Showing 11 to 20 of 22 results", timeout=LIVE_MS)
        assert bob_list.url == url_before
        rows = bob_list.get_by_test_id("list-row")
        expect(rows).to_have_count(10)
        expect(rows.first).to_contain_text("Article 22")
        assert errors == []


def test_row_scoping_is_respected(browser: Browser, notif_url: str) -> None:
    """
    Scenario: row scoping is respected
      Given NoteAdmin.get_queryset limits each user to the Notes they own
      When  A creates a Note
      Then  B's refreshed list does not contain it
      And   B's pagination total is unchanged
    """
    # Given bob sees only his three notes
    with _sessions(browser, notif_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, notif_url, "/admin/note")
        expect(_total(bob_list)).to_contain_text("of 3 results")
        refetches = _hx_list_requests(bob_list, "/admin/note")

        # When alice creates a Note she owns (user id 1)
        pk = _create(alice, notif_url, "/admin/note", Title="alice secret", Owner="1")

        # Then bob's list is re-fetched (the event reached him) but never shows the row
        bob_list.wait_for_timeout(QUIET_MS)
        assert refetches, "bob's Note list never re-fetched"
        expect(_row(bob_list, pk)).to_have_count(0)
        expect(bob_list.get_by_text("alice secret")).to_have_count(0)
        # And his total is unchanged
        expect(_total(bob_list)).to_contain_text("of 3 results")
        assert errors == []


def test_no_subscription_attempt_without_view_permission(browser: Browser, notif_url: str) -> None:
    """
    Scenario: no subscription attempt without view permission
      Given B lacks the view permission on Article
      When  B opens any admin page
      Then  no page renders an Article subscription hook
      And   B's socket sends no subscribe frame for Article
    """
    # Given carol holds no permission at all
    with _sessions(browser, notif_url, "carol") as ((carol,), errors):
        # When she opens the admin home and the Article list (refused)
        home = carol.new_page()
        home.goto(f"{notif_url}/admin/")
        forbidden = carol.new_page()
        response = forbidden.goto(f"{notif_url}{ARTICLES}")
        assert response is not None
        assert response.status == 403
        home.wait_for_timeout(QUIET_MS)

        # Then no page renders a subscription hook
        expect(home.get_by_test_id(HOOK)).to_have_count(0)
        expect(forbidden.get_by_test_id(HOOK)).to_have_count(0)
        # And her sockets send no subscribe frame
        assert _sent_subscribes(home) == []
        assert _sent_subscribes(forbidden) == []
        assert errors == []


def test_forged_subscription_is_refused(browser: Browser, notif_url: str) -> None:
    """
    Scenario: forged subscription is refused
      Given B lacks the view permission on Article
      When  B's socket sends a hand-crafted subscribe frame for Article
      Then  the server refuses it and B receives no Article events
    """
    # Given carol (no permission) and bob (allowed, as a control) on any admin page
    with _sessions(browser, notif_url, "alice", "bob", "carol") as ((alice, bob, carol), errors):
        carol_home = carol.new_page()
        carol_home.goto(f"{notif_url}/admin/")
        bob_home = bob.new_page()
        bob_home.goto(f"{notif_url}/admin/")

        # When both send a hand-made subscribe frame for Article
        _forge(carol_home, notif_url, "article")
        _forge(bob_home, notif_url, "article")
        # And alice creates an Article
        pk = _create(alice, notif_url, ARTICLES, Title="Forged target")

        # Then bob's socket is served the event while carol's gets nothing
        bob_home.wait_for_function(
            "() => window.__forged.some((f) => f.includes('\"crud\"'))", timeout=LIVE_MS
        )
        assert any(f["type"] == "crud" and f["pk"] == pk for f in _forged_frames(bob_home)), (
            _forged_frames(bob_home)
        )
        carol_home.wait_for_timeout(QUIET_MS)
        assert [f for f in _forged_frames(carol_home) if f.get("type") == "crud"] == []
        assert errors == []


def test_realtime_disabled_is_a_no_op(browser: Browser, off_url: str) -> None:
    """
    Scenario: realtime disabled is a no-op
      Given Admin(realtime=None)
      When  any record is created, updated or deleted
      Then  nothing is published and list pages render no realtime hooks
    """
    # Given realtime is off; bob has the Article list open
    with _sessions(browser, off_url, "alice", "bob") as ((alice, bob), errors):
        bob_list = _open_list(bob, off_url)

        # When alice creates an Article
        pk = _create(alice, off_url, ARTICLES, Title="Unannounced")

        # Then bob's list renders no hook, no status widget and never changes by itself
        bob_list.wait_for_timeout(QUIET_MS)
        expect(bob_list.get_by_test_id(HOOK)).to_have_count(0)
        expect(bob_list.get_by_test_id("realtime-status")).to_have_count(0)
        expect(_row(bob_list, pk)).to_have_count(0)
        expect(_toast(bob_list)).to_have_count(0)
        assert _sent_subscribes(bob_list) == []
        assert errors == []
