"""Behaviour of the ``views.dynamic`` package that no other unit test pins.

Covers the error, redirect and re-render branches of the action, create, update,
inline, file, popup and saved-view handlers. The app is driven through
``httpx.ASGITransport`` so the handlers run on the test's own event loop (and are
traced by coverage), then a few collaborators are exercised directly.
"""

import logging
import os
import tempfile
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import MagicMock
from urllib.parse import urlencode

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType
from pydantic import BaseModel, NaiveDatetime
from sqlalchemy import Column, DateTime, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, Relationship, SQLModel
from starlette.responses import Response

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.adapters import InlineRowNotOwnedError
from hyperadmin.core.choices import SelectFieldMeta
from hyperadmin.core.display import get_display_name
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions, RelationDependency
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import HyperAdminRouter
from hyperadmin.views import dynamic as dynamic_module
from hyperadmin.views.dynamic import base as base_module
from hyperadmin.views.dynamic import relations as relations_module
from hyperadmin.views.dynamic.files import FileViewMixin
from hyperadmin.views.dynamic.model_view import ModelView

pytestmark = pytest.mark.anyio

_STORAGE_ROOT = tempfile.mkdtemp(prefix="hyperadmin-uncovered-")
_storage = FileSystemStorage(_STORAGE_ROOT)


class UcOrder(SQLModel, table=True):
    __tablename__ = "uc_order"

    id: int | None = Field(default=None, primary_key=True)
    status: str = "new"
    notes: str = Field(default="", min_length=3)
    updated_at: NaiveDatetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(),  # type: ignore[call-overload]
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
    )

    lines: list["UcLine"] = Relationship(back_populates="order")


class UcLine(SQLModel, table=True):
    __tablename__ = "uc_line"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int | None = Field(default=None, foreign_key="uc_order.id")
    sku: str = ""
    qty: int = 1

    order: Optional[UcOrder] = Relationship(back_populates="lines")  # noqa: UP045


class UcDoc(SQLModel, table=True):
    __tablename__ = "uc_doc"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    pdf: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))


class UcSecret(SQLModel, table=True):
    __tablename__ = "uc_secret"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""
    password: str = ""


class UcFalsy(SQLModel, table=True):
    """A record that reads as falsy while its name is empty (like an empty collection)."""

    __tablename__ = "uc_falsy"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""

    def __bool__(self) -> bool:
        return bool(self.name)


class _ReassignParams(BaseModel):
    operator: int


class UcOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter
    form_columns = ["status", "notes"]
    form_create_exclude = ["status"]

    @action(label="Archive")
    async def archive(self, request: Request, item_id: Any) -> None:
        return None

    @action(label="Close all", bulk=True)
    async def close_all(self, request: Request, item_id: Any, *, params: Any = None) -> None:
        return None

    @action(label="Reassign", bulk=True, form=_ReassignParams)
    async def reassign(self, request: Request, item_id: Any, *, params: Any = None) -> None:
        return None


class UcLineAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class UcDocAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _User:
    is_superuser = False


class _AllowAll:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return True


class _RequestState:
    """Pure ASGI middleware that signs a user in by seeding ``request.state``."""

    def __init__(self, app: Any, user: Any = None) -> None:
        self.app = app
        self.user = user

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            state = scope.setdefault("state", {})
            state["user_key"] = "1"
            if self.user is not None:
                state["user"] = self.user
        await self.app(scope, receive, send)


class _PermAdmin(Admin):
    """``Admin`` that enforces ``permission_checker`` without a full auth backend."""

    def _register_views(self) -> None:
        router = HyperAdminRouter(
            engine=self.engine,
            templates=self.templates,
            permission_checker=self.permission_checker,
            storage=self.storage,
        )
        router.generate_routes()
        for r in router.get_routers():
            self.router.include_router(r)


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    site._registry = {}
    yield
    site._registry = {}


def _stored_file(name: str) -> Path:
    path = Path(_STORAGE_ROOT) / name
    path.write_bytes(b"payload")
    return path


async def _seed(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO uc_order (id, status, notes, updated_at) VALUES "
                "(1, 'new', '', '2026-01-01 00:00:00'), (2, 'new', 'okay', '2026-01-01 00:00:00')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO uc_line (id, order_id, sku, qty) VALUES "
                "(10, 1, 'line-10', 1), (20, 2, 'line-20', 2)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO uc_doc (id, title, pdf) VALUES "
                "(1, 'd1', 'uc-doc1.txt'), (2, 'd2', 'uc-doc2.txt')"
            )
        )


async def _scalar(engine: AsyncEngine, sql: str) -> Any:
    async with engine.connect() as conn:
        row = (await conn.execute(text(sql))).first()
    return row[0] if row else None


class _Harness:
    def __init__(self, client: httpx.AsyncClient, engine: AsyncEngine) -> None:
        self.client = client
        self.engine = engine


async def _open(
    *,
    permission_checker: Any = None,
    user: Any = None,
    register_line: bool = False,
    storage: Any = _storage,
) -> tuple[FastAPI, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)
    app = FastAPI()

    app.add_middleware(_RequestState, user=user)

    admin_cls = _PermAdmin if permission_checker is not None else Admin
    admin = admin_cls(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        permission_checker=permission_checker,
        storage=storage,
    )
    site.register(
        UcOrder,
        UcOrderAdmin,
        options=AdminOptions(
            list_editable=["status", "updated_at"],
            saved_views_enabled=True,
            inlines=[InlineModelSpec(model=UcLine, fk_field="order_id", relationship_name="lines")],
        ),
    )
    site.register(UcDoc, UcDocAdmin)
    if register_line:
        site.register(UcLine, UcLineAdmin)
    admin.mount(path="/admin")
    return app, engine


@pytest.fixture
async def http() -> AsyncIterator[_Harness]:
    app, engine = await _open()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield _Harness(client, engine)
    await engine.dispose()


@pytest.fixture
async def http_authed() -> AsyncIterator[_Harness]:
    app, engine = await _open(permission_checker=_AllowAll(), user=_User(), register_line=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield _Harness(client, engine)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Row and bulk actions
# ---------------------------------------------------------------------------


async def test_unknown_row_action_is_404(http: _Harness) -> None:
    """
    Scenario: a row action that is not registered
      Given an admin with an @action named "archive"
      When  POST /admin/ucorder/1/action/nope
      Then  the response is 404 naming the action
    """
    resp = await http.client.post("/admin/ucorder/1/action/nope")

    assert resp.status_code == 404
    assert "nope" in resp.json()["detail"]


async def test_row_action_from_htmx_redirects_to_the_list_with_hx_redirect(
    http: _Harness,
) -> None:
    """
    Scenario: a row action triggered by HTMX
      Given a handler that returns nothing
      When  POST /admin/ucorder/1/action/archive carries HX-Request
      Then  the response is 200 with an HX-Redirect to the model list
    """
    resp = await http.client.post("/admin/ucorder/1/action/archive", headers={"HX-Request": "true"})

    assert resp.status_code == 200
    assert resp.headers["HX-Redirect"].endswith("/admin/ucorder")


async def test_bulk_confirm_on_an_action_without_a_form_is_404(http: _Harness) -> None:
    """
    Scenario: confirming a bulk action that has no parameter form
      Given a bulk action declared without a Pydantic form
      When  POST /admin/ucorder/actions/close_all/bulk/confirm
      Then  the response is 404 because there is no confirm step
    """
    resp = await http.client.post(
        "/admin/ucorder/actions/close_all/bulk/confirm", data={"ids": "1"}
    )

    assert resp.status_code == 404
    assert "no confirm step" in resp.json()["detail"]


async def test_bulk_confirm_without_a_selection_is_400(http: _Harness) -> None:
    """
    Scenario: confirming a bulk action with nothing selected
      Given a bulk action with a parameter form that requires a selection
      When  POST /admin/ucorder/actions/reassign/bulk/confirm with no ids
      Then  the response is 400 "Selection required"
    """
    resp = await http.client.post(
        "/admin/ucorder/actions/reassign/bulk/confirm", data={"operator": "3"}
    )

    assert resp.status_code == 400
    assert "Selection required" in resp.text


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_permission_checked_admin_rejects_a_request_without_a_user() -> None:
    """
    Scenario: permission checks need a signed-in user
      Given an admin configured with a permission_checker
      When  a request reaches a model page with no request.state.user
      Then  the response is 403 "Authentication required"
    """
    app, engine = await _open(permission_checker=_AllowAll())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/admin/ucorder/create")
    await engine.dispose()

    assert resp.status_code == 403
    assert "Authentication required" in resp.text


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_form_omits_fields_in_form_create_exclude(http: _Harness) -> None:
    """
    Scenario: form_create_exclude hides a field on the create form only
      Given form_columns = [status, notes] and form_create_exclude = [status]
      When  GET /admin/ucorder/create
      Then  the notes input is rendered and the status input is not
    """
    resp = await http.client.get("/admin/ucorder/create")

    assert resp.status_code == 200
    assert 'name="notes"' in resp.text
    assert 'name="status"' not in resp.text


async def test_create_ignores_fields_in_form_create_exclude(http: _Harness) -> None:
    """
    Scenario: creating a row with an excluded field
      Given form_create_exclude = [status]
      When  POST /admin/ucorder with notes only
      Then  the row is created with the default status and the user is redirected
    """
    resp = await http.client.post("/admin/ucorder", data={"notes": "fresh"})

    assert resp.status_code == 303
    assert await _scalar(http.engine, "SELECT status FROM uc_order WHERE notes = 'fresh'") == "new"


async def test_create_with_a_parent_error_keeps_valid_inline_rows(http: _Harness) -> None:
    """
    Scenario: a parent validation error re-renders the submitted inline rows
      Given an order with an inline line formset
      When  POST /admin/ucorder with notes too short and a valid inline row
      Then  the response is 422, nothing is stored and the inline row is shown again
    """
    resp = await http.client.post(
        "/admin/ucorder",
        data={"notes": "x", "ucline-0-sku": "kept-sku", "ucline-0-qty": "4"},
    )

    assert resp.status_code == 422
    assert "kept-sku" in resp.text
    assert await _scalar(http.engine, "SELECT COUNT(*) FROM uc_order") == 2


async def test_create_with_an_invalid_inline_row_rerenders_what_was_submitted(
    http: _Harness,
) -> None:
    """
    Scenario: an invalid inline row is shown again with the submitted value
      Given an order with an inline line formset
      When  POST /admin/ucorder with a valid parent and an inline qty that is not a number
      Then  the response is 422 and the bad qty is echoed back for correction
    """
    resp = await http.client.post(
        "/admin/ucorder",
        data={"notes": "valid", "ucline-0-sku": "s1", "ucline-0-qty": "not-a-number"},
    )

    assert resp.status_code == 422
    assert "not-a-number" in resp.text
    assert await _scalar(http.engine, "SELECT COUNT(*) FROM uc_order") == 2


async def test_create_with_an_empty_file_input_leaves_the_file_unset(http: _Harness) -> None:
    """
    Scenario: no file chosen on a file field
      Given a model with a file column
      When  POST /admin/ucdoc submits the form with an empty file input
      Then  the row is created and its file column stays empty
    """
    resp = await http.client.post(
        "/admin/ucdoc",
        data={"title": "no-file"},
        files={"pdf": ("", b"", "application/octet-stream")},
    )

    assert resp.status_code == 303
    assert await _scalar(http.engine, "SELECT pdf FROM uc_doc WHERE title = 'no-file'") is None


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_with_a_parent_error_keeps_valid_inline_rows(http: _Harness) -> None:
    """
    Scenario: a parent validation error on update re-renders the inline rows
      Given order 2 with an inline line
      When  PUT /admin/ucorder/2 with notes too short and an unchanged inline row
      Then  the response is 422 and the stored order is untouched
    """
    resp = await http.client.put(
        "/admin/ucorder/2",
        data={
            "status": "done",
            "notes": "x",
            "ucline-0-pk": "20",
            "ucline-0-sku": "resubmitted-sku",
            "ucline-0-qty": "2",
        },
    )

    assert resp.status_code == 422
    assert "resubmitted-sku" in resp.text
    assert await _scalar(http.engine, "SELECT status FROM uc_order WHERE id = 2") == "new"


async def test_update_changes_an_existing_inline_row_of_a_registered_model(
    http_authed: _Harness,
) -> None:
    """
    Scenario: editing an inline row needs the inline model's change permission
      Given the inline line model is registered and the user holds every permission
      When  PUT /admin/ucorder/2 resubmits line 20 with a new sku
      Then  the update succeeds and the line is renamed
    """
    resp = await http_authed.client.put(
        "/admin/ucorder/2",
        data={
            "status": "done",
            "notes": "okay",
            "ucline-0-pk": "20",
            "ucline-0-sku": "renamed",
            "ucline-0-qty": "2",
        },
    )

    assert resp.status_code == 303
    assert await _scalar(http_authed.engine, "SELECT sku FROM uc_line WHERE id = 20") == "renamed"


# ---------------------------------------------------------------------------
# Inline rows and in-list cell editing
# ---------------------------------------------------------------------------


async def test_inline_add_row_for_an_unknown_inline_is_404(http: _Harness) -> None:
    """
    Scenario: add-row for an inline the admin does not declare
      Given an order admin with a "ucline" inline
      When  GET /admin/ucorder/inline/nothing/add-row
      Then  the response is 404 naming the inline
    """
    resp = await http.client.get("/admin/ucorder/inline/nothing/add-row")

    assert resp.status_code == 404
    assert "nothing" in resp.json()["detail"]


async def test_inline_cell_editor_refuses_a_field_outside_list_editable(
    http: _Harness,
) -> None:
    """
    Scenario: only list_editable fields open a cell editor
      Given list_editable = [status]
      When  GET /admin/ucorder/1/inline/notes
      Then  the response is 403 "Field not editable"
    """
    resp = await http.client.get("/admin/ucorder/1/inline/notes")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Field not editable"


async def test_inline_cell_save_refuses_a_field_outside_list_editable(http: _Harness) -> None:
    """
    Scenario: only list_editable fields can be saved in place
      Given list_editable = [status]
      When  POST /admin/ucorder/1/inline/notes
      Then  the response is 403 and the stored value is unchanged
    """
    resp = await http.client.post("/admin/ucorder/1/inline/notes", data={"notes": "hacked"})

    assert resp.status_code == 403
    assert await _scalar(http.engine, "SELECT notes FROM uc_order WHERE id = 1") == ""


async def test_inline_cell_save_rejects_a_row_that_is_invalid_elsewhere(http: _Harness) -> None:
    """
    Scenario: the edited cell is valid but another field of the row is not
      Given order 1 stores notes shorter than the model allows
      When  POST /admin/ucorder/1/inline/status with a valid status
      Then  the response is 422 "Invalid value" and nothing is saved
    """
    resp = await http.client.post("/admin/ucorder/1/inline/status", data={"status": "done"})

    assert resp.status_code == 422
    assert "Invalid value" in resp.text
    assert await _scalar(http.engine, "SELECT status FROM uc_order WHERE id = 1") == "new"


async def test_inline_cell_editor_refuses_a_field_the_form_does_not_expose(
    http: _Harness,
) -> None:
    """
    Scenario: a list_editable field that the form hides
      Given list_editable names a field that stamps "now" and is hidden from forms
      When  GET /admin/ucorder/1/inline/updated_at
      Then  the response is 403 "Field not editable"
    """
    resp = await http.client.get("/admin/ucorder/1/inline/updated_at")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Field not editable"


async def test_inline_cell_save_refuses_a_field_the_form_does_not_expose(
    http: _Harness,
) -> None:
    """
    Scenario: saving a list_editable field that the form hides
      Given list_editable names a field that stamps "now" and is hidden from forms
      When  POST /admin/ucorder/1/inline/updated_at
      Then  the response is 403 and the stored timestamp is unchanged
    """
    resp = await http.client.post(
        "/admin/ucorder/1/inline/updated_at", data={"updated_at": "2030-01-01T00:00"}
    )

    assert resp.status_code == 403
    stored = await _scalar(http.engine, "SELECT updated_at FROM uc_order WHERE id = 1")
    assert str(stored).startswith("2026-01-01")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


async def test_upload_stores_the_file_and_returns_its_name(http: _Harness) -> None:
    """
    Scenario: uploading a file to a file field
      Given a model with a file column and a configured storage
      When  POST /admin/ucdoc/upload/pdf carries a file
      Then  the file is stored and the JSON response names it
    """
    resp = await http.client.post(
        "/admin/ucdoc/upload/pdf", files={"file": ("report.txt", b"hello", "text/plain")}
    )

    assert resp.status_code == 200
    name = resp.json()["filename"]
    assert name.endswith("-report.txt")
    assert (Path(_STORAGE_ROOT) / name).read_bytes() == b"hello"


async def test_upload_without_a_file_part_is_400(http: _Harness) -> None:
    """
    Scenario: upload request with no file
      Given a model with a file column
      When  POST /admin/ucdoc/upload/pdf has no "file" part
      Then  the response is 400 "No file provided"
    """
    resp = await http.client.post("/admin/ucdoc/upload/pdf", data={"other": "x"})

    assert resp.status_code == 400
    assert resp.json()["detail"] == "No file provided"


async def test_upload_whose_stored_name_already_exists_is_refused(
    http: _Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: an upload never overwrites an existing stored file
      Given the generated storage name is already taken
      When  POST /admin/ucdoc/upload/pdf
      Then  the response is 400 "Invalid file name" and the old file is intact
    """
    taken = _stored_file(f"taken-{os.getpid()}.txt")
    monkeypatch.setattr(FileViewMixin, "_new_upload_name", lambda self, client_name: taken.name)

    resp = await http.client.post(
        "/admin/ucdoc/upload/pdf", files={"file": ("new.txt", b"new", "text/plain")}
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid file name"
    assert taken.read_bytes() == b"payload"


async def test_delete_file_removes_it_from_storage_and_clears_the_column(
    http: _Harness,
) -> None:
    """
    Scenario: deleting the file of a record
      Given doc 1 has a stored file
      When  DELETE /admin/ucdoc/1/file/pdf
      Then  the file is gone from storage, the column is cleared and the answer is 204
    """
    stored = _stored_file("uc-doc1.txt")

    resp = await http.client.delete("/admin/ucdoc/1/file/pdf")

    assert resp.status_code == 204
    assert not stored.exists()
    assert await _scalar(http.engine, "SELECT pdf FROM uc_doc WHERE id = 1") is None


async def test_delete_file_from_htmx_announces_file_deleted(http: _Harness) -> None:
    """
    Scenario: deleting a file from an HTMX widget
      Given doc 2 has a stored file
      When  DELETE /admin/ucdoc/2/file/pdf carries HX-Request
      Then  the response is 200 with an HX-Trigger of fileDeleted
    """
    stored = _stored_file("uc-doc2.txt")

    resp = await http.client.delete("/admin/ucdoc/2/file/pdf", headers={"HX-Request": "true"})

    assert resp.status_code == 200
    assert resp.headers["HX-Trigger"] == "fileDeleted"
    assert not stored.exists()


async def test_deleting_a_record_removes_its_stored_files(http: _Harness) -> None:
    """
    Scenario: deleting a record cleans up its files
      Given doc 1 has a stored file
      When  DELETE /admin/ucdoc/1
      Then  the row and its stored file are both gone
    """
    stored = _stored_file("uc-doc1.txt")

    resp = await http.client.delete("/admin/ucdoc/1")

    assert resp.status_code == 303
    assert not stored.exists()
    assert await _scalar(http.engine, "SELECT COUNT(*) FROM uc_doc WHERE id = 1") == 0


# ---------------------------------------------------------------------------
# Create popup
# ---------------------------------------------------------------------------


async def test_popup_get_without_a_target_is_400(http: _Harness) -> None:
    """
    Scenario: opening the create popup without saying which widget asked
      Given an order admin
      When  GET /admin/ucorder/create-popup has no target query parameter
      Then  the response is 400 "target query param required"
    """
    resp = await http.client.get("/admin/ucorder/create-popup")

    assert resp.status_code == 400
    assert "target query param required" in resp.json()["detail"]


async def test_popup_form_omits_fields_in_form_create_exclude(http: _Harness) -> None:
    """
    Scenario: the popup create form honours form_create_exclude
      Given form_create_exclude = [status]
      When  GET /admin/ucorder/create-popup?target=order
      Then  the popup renders the notes input and not the status input
    """
    resp = await http.client.get("/admin/ucorder/create-popup", params={"target": "order"})

    assert resp.status_code == 200
    assert 'name="notes"' in resp.text
    assert 'name="status"' not in resp.text


async def test_popup_post_creates_a_row_without_excluded_fields(http: _Harness) -> None:
    """
    Scenario: the popup POST honours form_create_exclude
      Given form_create_exclude = [status]
      When  POST /admin/ucorder/create-popup with target and notes
      Then  the row is created with the default status
    """
    resp = await http.client.post(
        "/admin/ucorder/create-popup", data={"target": "order", "notes": "popup-made"}
    )

    assert resp.status_code == 200
    assert "hyperadminPopupCreated" in resp.headers["HX-Trigger"]
    assert (
        await _scalar(http.engine, "SELECT status FROM uc_order WHERE notes = 'popup-made'")
        == "new"
    )


# ---------------------------------------------------------------------------
# Saved views
# ---------------------------------------------------------------------------

_JSON = {"Accept": "application/json"}


async def test_saved_view_defaults_to_the_requests_own_querystring(http: _Harness) -> None:
    """
    Scenario: saving the list as it is on screen
      Given alice posts the save form from a filtered list without a querystring field
      When  POST /admin/ucorder/saved-views?status=late with only a name
      Then  the saved view keeps the request's own querystring
    """
    resp = await http.client.post(
        "/admin/ucorder/saved-views?status=late", data={"name": "Late"}, headers=_JSON
    )

    assert resp.status_code == 201
    assert resp.json()["querystring"] == "status=late"


async def test_saved_view_uses_the_querystring_field_when_posted(http: _Harness) -> None:
    """
    Scenario: saving an explicit querystring
      Given alice posts a name and a querystring field
      When  POST /admin/ucorder/saved-views?status=ignored
      Then  the saved view keeps the posted querystring, not the request's
    """
    resp = await http.client.post(
        "/admin/ucorder/saved-views?status=ignored",
        data={"name": "Done", "querystring": "?status=done"},
        headers=_JSON,
    )

    assert resp.status_code == 201
    assert resp.json()["querystring"] == "status=done"


async def test_saved_view_with_a_blank_name_is_422(http: _Harness) -> None:
    """
    Scenario: saving a view without a name
      Given alice posts a blank name
      When  POST /admin/ucorder/saved-views
      Then  the response is 422 and nothing is saved
    """
    resp = await http.client.post("/admin/ucorder/saved-views", data={"name": "   "}, headers=_JSON)

    assert resp.status_code == 422
    assert await _scalar(http.engine, "SELECT COUNT(*) FROM hyperadmin_saved_view") == 0


# ---------------------------------------------------------------------------
# Collaborators exercised directly
# ---------------------------------------------------------------------------


def _view(
    model: type[SQLModel], options: AdminOptions | None = None, *, storage: Any = None
) -> dynamic_module.DynamicModelView:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return dynamic_module.DynamicModelView(
        adapter=SQLModelAdapter(model, engine),
        options=options or AdminOptions(),
        templates=MagicMock(),
        app_label=None,
        storage=storage,
    )


def _request(data: dict[str, str] | None = None, method: str = "POST") -> Request:
    body = urlencode(data or {}).encode()

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "query_string": b"",
        "scheme": "http",
        "server": ("test", 80),
        "headers": [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    return Request(scope, receive)


def test_model_view_remembers_the_model_it_was_built_for() -> None:
    """
    Scenario: instantiating a ModelView
      Given a ModelView subclass without a registered model
      When  it is instantiated with a model class
      Then  the instance exposes that model
    """

    class PlainAdmin(ModelView):
        pass

    assert PlainAdmin(UcOrder).model is UcOrder


def test_cascade_keys_include_the_parent_of_a_relation_filter() -> None:
    """
    Scenario: relation_filters declares a dependent select
      Given relation_filters = {order_id: depends_on region_id}
      When  the declared cascade keys of the "order" relation are collected
      Then  the parent field "region_id" is accepted
    """
    options = AdminOptions(
        relation_filters={"order_id": RelationDependency(depends_on="region_id")}
    )

    assert _view(UcLine, options)._declared_cascade_keys("order") == {"region_id"}


def test_cascade_keys_include_the_parent_declared_on_the_field_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a field's select metadata declares its parent
      Given the FK field classifies as a relation select with dependent_on="region_id"
      When  the declared cascade keys of the "order" relation are collected
      Then  the parent field "region_id" is accepted
    """
    meta = SelectFieldMeta(choices_source="relation", dependent_on="region_id")
    monkeypatch.setattr(base_module, "classify_field", lambda field_info, model: meta)

    assert _view(UcLine)._declared_cascade_keys("order") == {"region_id"}


def test_stored_secrets_ignore_sensitive_overrides_that_are_not_model_fields() -> None:
    """
    Scenario: a sensitive override names a field the model does not have
      Given sensitive_fields = {ghost: True} on a model with a password field
      When  an update submits an empty password
      Then  the stored password is kept and no "ghost" key appears
    """
    view = _view(UcSecret, AdminOptions(sensitive_fields={"ghost": True}))
    data = {"name": "n", "password": ""}

    view._keep_stored_secrets(data, SimpleNamespace(password="stored"))

    assert data == {"name": "n", "password": "stored"}


def test_inline_add_row_url_is_empty_when_the_route_cannot_be_resolved() -> None:
    """
    Scenario: inline formsets built outside a mounted admin
      Given an admin with an inline and a request that cannot resolve routes
      When  the inline formsets are built
      Then  the formset has an empty add_row_url instead of failing
    """
    spec = InlineModelSpec(model=UcLine, fk_field="order_id", relationship_name="lines")
    view = _view(UcOrder, AdminOptions(inlines=[spec]))

    formsets = view._build_inline_formsets(request=SimpleNamespace())  # type: ignore[arg-type]

    assert [f.add_row_url for f in formsets] == [""]


async def test_saving_inline_rows_turns_a_lost_ownership_race_into_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: an inline child is reparented between the check and the write
      Given the adapter reports a submitted child is no longer owned by the parent
      When  the inline rows are saved
      Then  the view answers 404 "Inline row not found"
    """
    spec = InlineModelSpec(model=UcLine, fk_field="order_id", relationship_name="lines")
    view = _view(UcOrder, AdminOptions(inlines=[spec]))

    async def lost_race(spec: Any, rows: Any, parent_pk: Any) -> None:
        raise InlineRowNotOwnedError("moved")

    monkeypatch.setattr(view.adapter, "save_inline_rows", lost_race)

    with pytest.raises(HTTPException) as caught:
        await view._save_inline_rows([(view._inline_formset(spec), [])], parent_pk=1)

    assert caught.value.status_code == 404
    assert caught.value.detail == "Inline row not found"


async def test_upload_without_configured_storage_is_400() -> None:
    """
    Scenario: uploading to an admin that has no storage
      Given a view over a model with a file column but no storage
      When  an upload is posted to that file field
      Then  the view answers 400 "File uploads not configured"
    """
    view = _view(UcDoc, storage=None)

    with pytest.raises(HTTPException) as caught:
        await view.upload_file_view(_request(), "pdf")

    assert caught.value.status_code == 400
    assert caught.value.detail == "File uploads not configured"


async def test_create_rerenders_with_422_when_validation_yields_a_falsy_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: validation yields no usable instance and no field errors
      Given a model whose instances are falsy while their name is empty
      When  the create form is posted with an empty name
      Then  nothing is stored and the form is re-rendered with status 422
    """
    view = _view(UcFalsy)
    seen: dict[str, Any] = {}

    async def rerender(request: Any, **kwargs: Any) -> Response:
        seen.update(kwargs)
        return Response("re-rendered", status_code=kwargs["status_code"])

    monkeypatch.setattr(view, "create_form_view", rerender)

    resp = await view.create_view(_request({"name": ""}))

    assert resp.status_code == 422
    assert seen["values"] == {"name": ""}


async def test_update_rerenders_with_422_when_validation_yields_a_falsy_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: validation yields no usable instance on update
      Given an existing, truthy row of a model whose empty-named instances are falsy
      When  the edit form is submitted with an empty name
      Then  the row is not written and the form is re-rendered with status 422
    """
    view = _view(UcFalsy)
    engine = view.adapter.engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(text("INSERT INTO uc_falsy (id, name) VALUES (1, 'before')"))
    seen: dict[str, Any] = {}

    async def rerender(request: Any, **kwargs: Any) -> Response:
        seen.update(kwargs)
        return Response("re-rendered", status_code=kwargs["status_code"])

    monkeypatch.setattr(view, "update_form_view", rerender)

    resp = await view.update_view(_request({"name": ""}, method="PUT"), item_id=1)

    assert resp.status_code == 422
    assert seen["item_id"] == 1
    assert await _scalar(engine, "SELECT name FROM uc_falsy WHERE id = 1") == "before"
    await engine.dispose()


async def test_relation_widget_without_preload_or_autocomplete_starts_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Scenario: a lazy relation select without the autocomplete widget
      Given a relation field that does not preload and use_autocomplete_widget off
      When  the relation widgets are built
      Then  the widget starts with no options and loads them from the choices URL
    """
    meta = SelectFieldMeta(choices_source="relation", preload=False)
    monkeypatch.setattr(relations_module, "classify_field", lambda field_info, model: meta)

    view = _view(UcLine, AdminOptions(use_autocomplete_widget=False))
    widgets = await view._build_relation_widgets(field_names=["order_id"])

    assert widgets["order_id"].preload is False
    assert widgets["order_id"].choices == []


def test_relation_label_defaults_to_the_display_name_without_relation_display() -> None:
    """
    Scenario: no relation_display entry for the target field
      Given an admin without a relation_display entry for "order"
      When  the option label of a related row is resolved
      Then  it is the row's display name
    """
    line = UcLine(id=3, sku="sku-3")

    assert _view(UcOrder)._resolve_relation_label(line, "order") == get_display_name(line)


def test_relation_label_falls_back_when_the_display_callable_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a relation_display callable raises
      Given relation_display["order"] is a callable that raises
      When  the option label is resolved
      Then  the display name is used and a warning is logged
    """
    line = UcLine(id=3, sku="sku-3")

    def broken(instance: Any) -> str:
        raise RuntimeError("boom")

    options = AdminOptions(relation_display={"order": broken})
    with caplog.at_level(logging.WARNING):
        label = _view(UcOrder, options)._resolve_relation_label(line, "order")

    assert label == get_display_name(line)
    assert "relation_display callable" in caplog.text


def test_relation_label_falls_back_when_the_display_template_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: a relation_display template cannot be formatted
      Given relation_display["order"] is a template with a numeric format on a string
      When  the option label is resolved
      Then  the display name is used and a warning is logged
    """
    line = UcLine(id=3, sku="sku-3")
    options = AdminOptions(relation_display={"order": "{sku:d}"})

    with caplog.at_level(logging.WARNING):
        label = _view(UcOrder, options)._resolve_relation_label(line, "order")

    assert label == get_display_name(line)
    assert "relation_display template" in caplog.text
