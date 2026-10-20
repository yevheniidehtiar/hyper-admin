"""Rendering tests for the list-view bulk UI (H3, v0.5.5).

Mirrors the scenarios in
``.meta/epics/epic-v055-bulk-actions/stories/feattemplates-add-checkbox-column-and-bulk-toolbar.md``:
the checkbox column and toolbar appear only when a ``bulk=True`` action exists,
and the result grid renders one row per outcome with a "Retry failures" form.
"""

from __future__ import annotations

import re

import anyio
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

_fail_ids: set[int] = set()
_forbid_ids: set[int] = set()


class _ReassignParams(BaseModel):
    operator: int


class BulkUiProduct(SQLModel, table=True):
    __tablename__ = "test_bulk_ui_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class PlainProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Publish")
    async def publish(self, request: Request, item_id: int) -> None:
        return None


class BulkProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Archive", bulk=True)
    async def archive(self, request: Request, item_id: int, *, params=None) -> None:
        if item_id in _fail_ids:
            raise RuntimeError("x")
        if item_id in _forbid_ids:
            raise HTTPException(status_code=403, detail="Not yours to archive.")

    @action(label="Archive overdue", bulk=True, requires_selection=False)
    async def archive_overdue(self, request: Request, item_id: int, *, params=None) -> None:
        return None

    @action(label="Publish")
    async def publish(self, request: Request, item_id: int) -> None:
        return None

    @action(label="Reassign", bulk=True, form=_ReassignParams)
    async def reassign(self, request: Request, item_id: int, *, params=None) -> None:
        """Moves the products to another owner. Customers are not notified."""
        return


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    _fail_ids.clear()
    _forbid_ids.clear()
    yield
    site._registry = {}


def _client(admin_class: type[ModelAdmin], extra_rows: int = 0) -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            for name in ("alpha", "beta", "gamma"):
                session.add(BulkUiProduct(name=name))
            for index in range(extra_rows):
                session.add(BulkUiProduct(name=f"row-{index}"))
            await session.commit()

    anyio.run(setup_database)

    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(BulkUiProduct, admin_class)
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_view_without_bulk_actions_hides_the_checkbox_column():
    """
    Scenario: list view without bulk actions hides the checkbox column
      Given a ModelAdmin with no @action(bulk=True)
      When  the user opens the list view
      Then  the rendered table has no element with data-testid="bulk-checkbox"
    """
    # Given
    client = _client(PlainProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/")

    # Then
    assert response.status_code == 200
    assert 'data-testid="list-row"' in response.text
    assert 'data-testid="bulk-checkbox"' not in response.text
    assert 'data-testid="bulk-select-all"' not in response.text
    assert 'data-testid="bulk-action-select"' not in response.text


def test_list_view_with_a_bulk_action_renders_the_toolbar():
    """
    Scenario: list view with at least one bulk action renders the toolbar
      Given a ModelAdmin with @action(label="Archive", bulk=True)
      When  the user opens the list view
      Then  the toolbar shows a bulk-action-select containing option "Archive"
      And   each row has data-testid="bulk-checkbox"
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/")

    # Then
    html = response.text
    assert response.status_code == 200
    select = re.search(r'<select[^>]*data-testid="bulk-action-select".*?</select>', html, re.DOTALL)
    assert select is not None
    options = re.findall(r"<option[^>]*>([^<]*)</option>", select.group(0))
    # A placeholder first, then only bulk actions; the single-record "Publish"
    # action is not offered, and an action that opens a form ends in "…".
    assert options == ["Choose an action…", "Archive", "Archive overdue", "Reassign…"]
    assert 'data-url="http://testserver/admin/bulkuiproduct/actions/archive/bulk"' in html
    assert 'data-requires-selection="true"' in html
    assert 'data-requires-selection="false"' in html
    assert html.count('data-testid="list-row"') == 3
    assert html.count('data-testid="bulk-checkbox"') == 3
    checkboxes = re.findall(r'<input[^>]*data-testid="bulk-checkbox"[^>]*>', html)
    assert all('form="bulk-action-form"' in box for box in checkboxes)
    assert sorted(re.search(r'value="(\d+)"', box).group(1) for box in checkboxes) == [
        "1",
        "2",
        "3",
    ]
    assert 'data-testid="bulk-run-btn"' in html
    assert 'data-testid="bulk-select-all"' in html


def test_htmx_list_partial_keeps_the_checkbox_column():
    """
    Scenario: paging or sorting through htmx keeps the checkbox column
      Given a ModelAdmin with a bulk action
      When  the list table is re-fetched as an htmx partial
      Then  each row still has data-testid="bulk-checkbox"
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.get("/admin/bulkuiproduct/", headers={"HX-Request": "true"})

    # Then
    assert response.text.count('data-testid="bulk-checkbox"') == 3
    assert 'data-testid="bulk-bar"' in response.text


def test_result_page_renders_a_row_per_outcome_with_a_retry_form():
    """
    Scenario: result page renders a row per outcome
      Given run_bulk_action returns ok for id 1 and failed for id 2
      When  the result template renders
      Then  the page has two bulk-result-row entries
      And   the "Retry failures" form targets the bulk endpoint with ids=[2]
    """
    # Given
    client = _client(BulkProductAdmin)
    _fail_ids.add(2)

    # When
    response = client.post(
        "/admin/bulkuiproduct/actions/archive/bulk",
        data={"ids": ["1", "2"]},
        headers={"HX-Request": "true"},
    )

    # Then
    html = response.text
    assert response.status_code == 200
    assert html.count('data-testid="bulk-result-row"') == 2
    retry = re.search(r'<form[^>]*data-testid="bulk-retry-form".*?</form>', html, re.DOTALL)
    assert retry is not None
    assert 'hx-post="http://testserver/admin/bulkuiproduct/actions/archive/bulk"' in retry.group(0)
    assert 'hx-target="#bulk-result-region"' in retry.group(0)
    assert re.findall(r'name="ids" value="([^"]*)"', retry.group(0)) == ["2"]
    assert 'data-testid="bulk-retry-link"' in retry.group(0)


def test_result_page_omits_retry_when_every_row_succeeds():
    """
    Scenario: result page without failures has no "Retry failures" link
      Given every selected row succeeds
      When  the result template renders
      Then  no bulk-retry-link is rendered
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.post("/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ["1", "2"]})

    # Then
    assert response.text.count('data-testid="bulk-result-row"') == 2
    assert 'data-testid="bulk-retry-link"' not in response.text


# ---------------------------------------------------------------------------
# Design system (#664): BulkActionFlow states
# ---------------------------------------------------------------------------


def test_bulk_bar_reads_right_without_javascript():
    """
    Scenario: the bulk bar is complete without JavaScript
      Given a ModelAdmin with a bulk action
      When  the list view renders
      Then  the bar carries the no-script count copy, a Clear selection
            button and a hidden warning with role="alert"
      And   each row checkbox has an accessible "Select <pk>" name
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    html = client.get("/admin/bulkuiproduct/").text

    # Then
    assert 'data-testid="bulk-bar"' in html
    assert "Select rows, then choose an action" in html
    assert 'data-testid="bulk-clear-btn"' in html
    warning = re.search(r'<p[^>]*data-testid="bulk-warning"[^>]*>', html)
    assert warning is not None
    assert 'role="alert"' in warning.group(0)
    assert "hidden" in warning.group(0)
    assert "Select at least one row, then press Run." in html
    assert html.count("Select 1</span>") == 1
    assert 'aria-label="Select all rows on this page"' in html


def test_htmx_bulk_form_is_retargeted_into_the_dialog():
    """
    Scenario: with HTMX the parameter step opens in the dialog
      Given a bulk action with a parameter form
      When  the bar posts ids=[1,2] with an HX-Request header
      Then  the response is the bare form fragment (no page chrome)
      And   HX-Retarget points at #ha-popup-root with an innerHTML reswap
      And   the title repeats verb and count, the lede is the handler's
            docstring, and Cancel closes the popup
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.post(
        "/admin/bulkuiproduct/actions/reassign/bulk",
        data={"ids": ["1", "2"]},
        headers={"HX-Request": "true"},
    )

    # Then
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#ha-popup-root"
    assert response.headers["HX-Reswap"] == "innerHTML"
    html = response.text
    assert "<!DOCTYPE html>" not in html
    assert ">Reassign 2 rows</h2>" in html
    assert "Moves the products to another owner." in html
    assert '<li class="ha-mono">1</li>' in html
    cancel = re.search(r'<button[^>]*data-testid="bulk-cancel-btn"[^>]*>', html)
    assert cancel is not None
    assert "data-ha-popup-close" in cancel.group(0)
    assert 'data-testid="bulk-confirm-btn">Reassign 2 rows</button>' in html
    assert 'data-testid="bulk-form-field-operator"' in html
    assert '<span class="ha-req" aria-hidden="true">*</span>' in html


def test_plain_post_renders_the_bulk_form_as_a_page():
    """
    Scenario: without JavaScript the parameter step is a page with breadcrumbs
      Given a bulk action with a parameter form
      When  the bar posts one id without an HX-Request header
      Then  the response is a full page with a breadcrumb back to the list
      And   the title is singular and Cancel is a link to the list
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    response = client.post("/admin/bulkuiproduct/actions/reassign/bulk", data={"ids": ["1"]})

    # Then
    html = response.text
    assert response.status_code == 200
    assert "HX-Retarget" not in response.headers
    assert "<!DOCTYPE html>" in html
    assert 'data-testid="bulk-form-page"' in html
    assert 'data-testid="bulk-breadcrumb"' in html
    assert ">Reassign 1 row</h2>" in html
    cancel = re.search(r'<a[^>]*data-testid="bulk-cancel-btn"[^>]*>', html)
    assert cancel is not None
    assert 'href="http://testserver/admin/bulkuiproduct"' in cancel.group(0)


def test_bulk_form_validation_error_keeps_the_selection_and_explains():
    """
    Scenario: a validation error re-renders the step with an alert
      Given a bulk action with an int parameter
      When  the confirm endpoint receives a non-numeric value for ids=[1,2]
      Then  a danger alert says one field needs fixing and the rows are kept
      And   the field carries the message under its control and aria-describedby
      And   the hidden ids are still present
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    html = client.post(
        "/admin/bulkuiproduct/actions/reassign/bulk/confirm",
        data={"ids": ["1", "2"], "operator": "nope"},
    ).text

    # Then
    assert 'data-testid="bulk-form-alert"' in html
    assert "1 field needs fixing." in html
    assert "Your 2 selected rows are kept." in html
    assert 'aria-describedby="bulk-operator-errors"' in html
    assert 'class="ha-errmsg" id="bulk-operator-errors"' in html
    assert 'data-testid="bulk-form-operator-errors"' in html
    assert html.count('type="hidden" name="ids"') == 2


def test_bulk_result_lists_problems_first_with_status_words():
    """
    Scenario: the result page summarises and lists problems first
      Given archive fails on id 2 and is forbidden on id 3
      When  ids=[1,2,3] are posted without HTMX
      Then  the page is a full page, mixed tone, with a headline, a tally and
            a proportion bar
      And   rows are ordered 2, 3, 1 with the words Failed / Forbidden / Done
      And   the handler's 403 detail is shown as the row's explanation
      And   Retry failures carries both problem ids and Back links to the list
    """
    # Given
    client = _client(BulkProductAdmin)
    _fail_ids.add(2)
    _forbid_ids.add(3)

    # When
    response = client.post(
        "/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ["1", "2", "3"]}
    )

    # Then
    html = response.text
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in html
    assert 'data-testid="bulk-result-page"' in html
    assert 'class="ha-bulk-result ha-bulk-result--mixed"' in html
    assert "1 of 3 rows done. 1 failed and 1 not allowed." in html
    assert 'aria-label="1 done, 1 failed, 1 forbidden"' in html
    rows = re.findall(r'data-testid="bulk-result-status-(\d+)">(\w+)<', html)
    assert rows == [("2", "Failed"), ("3", "Forbidden"), ("1", "Done")]
    assert "Not yours to archive." in html
    assert "The action failed on this row." in html
    retry = re.search(r'<form[^>]*data-testid="bulk-retry-form".*?</form>', html, re.DOTALL)
    assert retry is not None
    assert re.findall(r'name="ids" value="([^"]*)"', retry.group(0)) == ["2", "3"]
    assert "Retry failures (2)" in retry.group(0)
    assert 'href="http://testserver/admin/bulkuiproduct/1"' in html
    back = re.search(r'<a[^>]*data-testid="bulk-back-link"[^>]*>', html)
    assert back is not None
    assert 'href="http://testserver/admin/bulkuiproduct"' in back.group(0)


def test_bulk_result_tones_for_all_done_and_all_failed():
    """
    Scenario: the headline and tone follow the outcome mix
      Given a formless bulk action
      When  every row succeeds
      Then  the result is the ok tone and says all rows are done, no retry
      When  every row fails
      Then  the result is the failed tone and says no rows are done
    """
    # Given
    client = _client(BulkProductAdmin)

    # When every row succeeds
    html = client.post("/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ["1", "2"]}).text

    # Then
    assert 'class="ha-bulk-result ha-bulk-result--ok"' in html
    assert "All 2 rows done." in html
    assert 'data-testid="bulk-retry-form"' not in html

    # When every row fails
    _fail_ids.update({1, 2})
    html = client.post("/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ["1", "2"]}).text

    # Then
    assert 'class="ha-bulk-result ha-bulk-result--failed"' in html
    assert "No rows done. 2 failed." in html


def test_bulk_result_folds_done_rows_above_twenty():
    """
    Scenario: long results keep the problems in view and fold the done rows
      Given 22 ids where only 1 and 3 exist and succeed, 2 fails and the
            rest are not found
      When  the result renders
      Then  the 20 problems stay in the main table, in plain words
      And   the 2 done rows sit inside a <details> labelled with their count
    """
    # Given
    client = _client(BulkProductAdmin)
    _fail_ids.add(2)
    ids = [str(i) for i in range(1, 23)]

    # When
    html = client.post("/admin/bulkuiproduct/actions/archive/bulk", data={"ids": ids}).text

    # Then
    assert html.count('data-testid="bulk-result-row"') == 22
    assert "Row not found. It may have been deleted after you selected it." in html
    assert 'data-testid="bulk-result-more"' in html
    assert "Show the 2 done rows" in html
    main_table = html[: html.index('data-testid="bulk-result-more"')]
    assert main_table.count('data-testid="bulk-result-row"') == 20


def test_bulk_result_without_selection_says_so():
    """
    Scenario: an action that does not require a selection ran over nothing
      Given a bulk action with requires_selection=False
      When  it is posted with no ids
      Then  the headline says no rows were selected and there is no bar
    """
    # Given
    client = _client(BulkProductAdmin)

    # When
    html = client.post("/admin/bulkuiproduct/actions/archive_overdue/bulk", data={"ids": []}).text

    # Then
    assert "No rows were selected." in html
    assert 'class="ha-progress__segments"' not in html


def test_bulk_result_fold_with_many_done_rows():
    """
    Scenario: more than twenty done rows fold into <details>
      Given 25 seeded rows and a formless bulk action
      When  all 25 ids are posted
      Then  the main table is empty of done rows and the details label counts 25
    """
    # Given
    client = _client(BulkProductAdmin, extra_rows=22)

    # When
    html = client.post(
        "/admin/bulkuiproduct/actions/archive/bulk", data={"ids": [str(i) for i in range(1, 26)]}
    ).text

    # Then
    assert 'data-testid="bulk-result-more"' in html
    assert "Show the 25 done rows" in html
    assert html.count('data-testid="bulk-result-row"') == 25
