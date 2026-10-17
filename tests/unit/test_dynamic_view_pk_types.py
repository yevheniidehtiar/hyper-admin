"""DynamicModelView item handlers for non-int primary keys (st-v058-byoa-29, BYOA SDD A.6).

Every item handler takes ``item_id: Any`` and resolves it through
``DynamicModelView._resolve_pk`` (``InvalidPrimaryKey`` → 404). List rows carry
``_pk`` (plus ``id`` when the model has one), every template context gets
``pk_attr``, and update keeps natural keys valid without ever rewriting the pk.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import anyio
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import Response

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import ActionDef
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.forms import InlineFormset

# ---------------------------------------------------------------------------
# Fixture models
# ---------------------------------------------------------------------------


class PkTypesUuidThing(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = "thing"


class PkTypesCodeThing(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    code: str = Field(primary_key=True)
    name: str = "thing"


class PkTypesIntThing(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = "thing"


class PkTypesUuidParent(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = "parent"


class PkTypesUuidChild(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="pktypesuuidparent.id")
    api_token: str = ""


class _ThingAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)
    return eng


def _seed(engine: Any, *rows: SQLModel) -> None:
    async def _add():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            for row in rows:
                session.add(row)
            await session.commit()

    anyio.run(_add)


def _all(engine: Any, model: type[SQLModel]) -> list[Any]:
    async def _fetch():
        async with AsyncSession(engine) as session:
            return list((await session.exec(select(model))).all())

    return anyio.run(_fetch)


def _mount(engine: Any, model: type[SQLModel], *, options: AdminOptions | None = None):
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(model, _ThingAdmin, options=options or AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app)


def _request(method: str = "GET", form_data: dict[str, Any] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/",
        "headers": [],
        "query_string": b"",
        "app": SimpleNamespace(
            url_path_for=lambda name, **kw: SimpleNamespace(
                make_absolute_url=lambda base_url=None, **kwargs: URL(f"/{name}")
            )
        ),
    }
    request = Request(scope)

    async def form():
        return form_data or {}

    request.form = form  # type: ignore[method-assign]
    return request


def _view(engine: Any, model: type[SQLModel], **kwargs: Any) -> tuple[DynamicModelView, MagicMock]:
    templates = MagicMock()
    templates.TemplateResponse.return_value = Response("ok")
    view = DynamicModelView(
        adapter=SQLModelAdapter(model, engine),
        options=kwargs.pop("options", AdminOptions()),
        templates=templates,
        app_label=None,
        **kwargs,
    )
    return view, templates


def _context(templates: MagicMock) -> dict[str, Any]:
    return templates.TemplateResponse.call_args.args[2]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_uuid_detail(engine):
    """
    Scenario: UUID detail
      Given a UUID row
      When  detail_view runs
      Then  the status is 200
    """
    row = PkTypesUuidThing(name="alpha")
    _seed(engine, row)
    client = _mount(engine, PkTypesUuidThing)

    response = client.get(f"/admin/pktypesuuidthing/{row.id}")

    assert response.status_code == 200
    assert "alpha" in response.text


def test_invalid_pk_update_404(engine):
    """
    Scenario: invalid pk update 404
      Given item_id='zzz' for a UUID model
      When  update_view runs
      Then  HTTP 404 is raised
    """
    view, _templates = _view(engine, PkTypesUuidThing)
    lookups: list[Any] = []

    async def _get(pk):
        lookups.append(pk)

    view.adapter.get = _get  # type: ignore[method-assign]

    with pytest.raises(HTTPException) as exc_info:
        anyio.run(view.update_view, _request("PUT", {"name": "x"}), "zzz")

    assert exc_info.value.status_code == 404
    # The malformed key is rejected by _resolve_pk, before any adapter lookup.
    assert lookups == []


def test_pk_not_overwritten(engine):
    """
    Scenario: pk not overwritten
      Given a UUID model
      When  update_view saves
      Then  the pk is not replaced by a fresh uuid4
    """
    row = PkTypesUuidThing(name="before")
    _seed(engine, row)
    client = _mount(engine, PkTypesUuidThing)

    response = client.put(
        f"/admin/pktypesuuidthing/{row.id}", data={"name": "after"}, follow_redirects=False
    )

    assert response.status_code == 303
    stored = _all(engine, PkTypesUuidThing)
    assert [(r.id, r.name) for r in stored] == [(row.id, "after")]


def test_natural_pk_update_validates(engine):
    """
    Scenario: natural pk update validates
      Given a natural str pk model
      When  update_view runs without a 'code' input
      Then  validation passes
    """
    _seed(engine, PkTypesCodeThing(code="abc", name="before"))
    client = _mount(engine, PkTypesCodeThing)

    response = client.put(
        "/admin/pktypescodething/abc", data={"name": "after"}, follow_redirects=False
    )

    assert response.status_code == 303
    stored = _all(engine, PkTypesCodeThing)
    assert [(r.code, r.name) for r in stored] == [("abc", "after")]


def _record_adapter_updates(view: DynamicModelView) -> list[tuple[Any, dict[str, Any]]]:
    """Replace ``view.adapter.update`` with a recorder that does not filter pk attrs."""
    calls: list[tuple[Any, dict[str, Any]]] = []

    async def _update(pk: Any, data: dict[str, Any]) -> None:
        calls.append((pk, dict(data)))

    view.adapter.update = _update  # type: ignore[method-assign]
    return calls


def test_update_view_strips_uuid_pk_before_adapter_update(engine):
    """
    Scenario: update_view never hands the uuid pk to the adapter
      Given a UUID row and an adapter whose update does not filter pk attributes
      When  update_view saves a new name
      Then  adapter.update receives the typed uuid.UUID pk
      And   the data passed to adapter.update has no 'id' key
    """
    row = PkTypesUuidThing(name="before")
    _seed(engine, row)
    view, _templates = _view(engine, PkTypesUuidThing)
    calls = _record_adapter_updates(view)

    anyio.run(view.update_view, _request("PUT", {"name": "after"}), str(row.id))

    ((pk, data),) = calls
    assert isinstance(pk, uuid.UUID)
    assert pk == row.id
    assert "id" not in data
    assert data["name"] == "after"


def test_update_view_strips_natural_pk_before_adapter_update(engine):
    """
    Scenario: update_view never hands the natural pk to the adapter
      Given a natural str pk row and an adapter whose update does not filter pk attributes
      When  update_view saves a new name
      Then  adapter.update receives the 'abc' pk
      And   the data passed to adapter.update has no 'code' key
    """
    _seed(engine, PkTypesCodeThing(code="abc", name="before"))
    view, _templates = _view(engine, PkTypesCodeThing)
    calls = _record_adapter_updates(view)

    anyio.run(view.update_view, _request("PUT", {"name": "after"}), "abc")

    ((pk, data),) = calls
    assert pk == "abc"
    assert "code" not in data
    assert data["name"] == "after"


def test_uuid_create_redirect(engine):
    """
    Scenario: UUID create redirect
      Given a UUID model
      When  create succeeds
      Then  the redirect goes to the new row's detail URL
    """
    client = _mount(engine, PkTypesUuidThing)

    response = client.post("/admin/pktypesuuidthing", data={"name": "new"}, follow_redirects=False)

    assert response.status_code == 303
    (created,) = _all(engine, PkTypesUuidThing)
    assert response.headers["location"].endswith(f"/admin/pktypesuuidthing/{created.id}")


def test_rows_keep_id(engine):
    """
    Scenario: rows keep id
      Given an int-id model
      When  list rows are built
      Then  each row has '_pk' and 'id'
    """
    _seed(engine, PkTypesIntThing(name="one"), PkTypesIntThing(name="two"))
    view, templates = _view(engine, PkTypesIntThing, column_list=["name"])

    anyio.run(view.list_view, _request(), 1, 10, "", None, "asc")

    rows = _context(templates)["items"]
    assert [(r["_pk"], r["id"]) for r in rows] == [(1, 1), (2, 2)]


# ---------------------------------------------------------------------------
# Supporting behaviour (SDD A.6)
# ---------------------------------------------------------------------------


def test_natural_pk_rows_carry_pk_but_no_id(engine):
    """
    Scenario: natural-key rows carry _pk only
      Given a str-pk model without an 'id' attribute
      When  list rows are built
      Then  each row has '_pk' set to the natural key and no 'id' key
      And   the context exposes pk_attr == 'code'
    """
    _seed(engine, PkTypesCodeThing(code="abc", name="one"))
    view, templates = _view(engine, PkTypesCodeThing)

    anyio.run(view.list_view, _request(), 1, 10, "", None, "asc")

    context = _context(templates)
    assert context["pk_attr"] == "code"
    (row,) = context["items"]
    assert row["_pk"] == "abc"
    assert "id" not in row
    # The default column list leads with the model's own pk attribute.
    assert view.column_list[0] == "code"


def test_detail_context_exposes_pk_attr(engine):
    """
    Scenario: detail context carries pk_attr
      Given a natural str pk row
      When  detail_view runs
      Then  the template context has pk_attr == 'code'
    """
    _seed(engine, PkTypesCodeThing(code="abc"))
    view, templates = _view(engine, PkTypesCodeThing)

    anyio.run(view.detail_view, _request(), "abc")

    assert _context(templates)["pk_attr"] == "code"


@pytest.mark.parametrize(
    "handler",
    [
        "detail_view",
        "update_form_view",
        "delete_action",
    ],
)
def test_invalid_pk_is_404_for_item_handlers(engine, handler):
    """
    Scenario: invalid pk 404 on every item handler
      Given item_id='zzz' for a UUID model
      When  the item handler runs
      Then  HTTP 404 is raised before any adapter work
    """
    view, _templates = _view(engine, PkTypesUuidThing)

    with pytest.raises(HTTPException) as exc_info:
        anyio.run(getattr(view, handler), _request(), "zzz")

    assert exc_info.value.status_code == 404


def test_invalid_pk_is_404_for_field_scoped_handlers(engine):
    """
    Scenario: invalid pk 404 on inline-edit, inline-save, delete-file and run-action
      Given item_id='zzz' for a UUID model with list_editable, a storage and an action
      When  each of those handlers runs
      Then  HTTP 404 is raised
    """

    async def _noop(self, request, item_id):
        return None

    action = ActionDef(name="ping", label="Ping", handler=_noop)
    storage = MagicMock()
    view, _templates = _view(
        engine,
        PkTypesUuidThing,
        options=AdminOptions(list_editable=["name"]),
        actions=[action],
        storage=storage,
    )
    view._get_file_fields = lambda: {"name"}  # type: ignore[method-assign]

    calls = [
        lambda: view.inline_edit_form_view(_request(), "zzz", "name", 0),
        lambda: view.inline_save_view(_request("POST", {"name": "x"}), "zzz", "name"),
        lambda: view.delete_file_view(_request("DELETE"), "zzz", "name"),
        lambda: view.run_action(_request("POST"), "zzz", "ping"),
    ]
    for call in calls:
        with pytest.raises(HTTPException) as exc_info:
            anyio.run(call)
        assert exc_info.value.status_code == 404


def test_run_action_receives_typed_uuid(engine):
    """
    Scenario: action handlers get the typed key
      Given a UUID row and a registered action
      When  run_action is called with the key as a string
      Then  the handler receives a uuid.UUID
    """
    row = PkTypesUuidThing()
    _seed(engine, row)
    seen: list[Any] = []

    async def _record(self, request, item_id):
        seen.append(item_id)
        return Response("done")

    view, _templates = _view(
        engine, PkTypesUuidThing, actions=[ActionDef(name="rec", label="Rec", handler=_record)]
    )

    anyio.run(view.run_action, _request("POST"), str(row.id), "rec")

    assert seen == [row.id]
    assert isinstance(seen[0], uuid.UUID)


def test_pk_attr_is_never_inline_editable(engine):
    """
    Scenario: natural pk is not inline-editable
      Given a str-pk model whose list_editable names the pk attribute
      When  the inline-edit allow-list is checked
      Then  the pk attribute is rejected and other fields are accepted
    """
    view, _templates = _view(
        engine, PkTypesCodeThing, options=AdminOptions(list_editable=["code", "name"])
    )

    assert view._is_inline_editable("code") is False
    assert view._is_inline_editable("name") is True


def test_popup_create_returns_uuid_as_json_string(engine):
    """
    Scenario: popup create with a UUID key
      Given a UUID model
      When  the create-popup POST succeeds
      Then  the HX-Trigger payload carries the new key as its canonical string
    """
    client = _mount(engine, PkTypesUuidThing)

    response = client.post(
        "/admin/pktypesuuidthing/create-popup", data={"target": "thing", "name": "pop"}
    )

    assert response.status_code == 200
    (created,) = _all(engine, PkTypesUuidThing)
    payload = json.loads(response.headers["HX-Trigger"])["hyperadminPopupCreated"]
    assert payload["id"] == str(created.id)


def test_popup_create_without_key_returns_null_id(engine):
    """
    Scenario: popup create whose new row has no key
      Given an adapter whose create() returns a row without a primary key value
      When  the create-popup POST succeeds
      Then  the HX-Trigger payload carries id null instead of raising
    """
    view, _templates = _view(engine, PkTypesIntThing)

    async def _create(data):
        return PkTypesIntThing(name="x")

    view.adapter.create = _create  # type: ignore[method-assign]
    response = anyio.run(view.create_popup_view, _request("POST", {"target": "thing", "name": "x"}))

    payload = json.loads(response.headers["HX-Trigger"])["hyperadminPopupCreated"]
    assert payload["id"] is None


def test_parse_ids_uses_pk_and_drops_invalid(engine):
    """
    Scenario: bulk ids are parsed with the model's pk
      Given a UUID model and submitted ids with one valid and one malformed value
      When  _parse_ids runs
      Then  only the valid id is returned, as a uuid.UUID
    """
    view, _templates = _view(engine, PkTypesUuidThing)
    key = uuid.uuid4()
    form = MagicMock()
    form.getlist.return_value = [str(key), "nope"]

    assert view._parse_ids(form, view.pk) == [key]


def test_create_view_redirects_to_list_when_new_row_has_no_key(engine):
    """
    Scenario: create without a resulting key
      Given an adapter whose create() returns a row without a primary key value
      When  create_view succeeds
      Then  the redirect goes to the list URL
    """
    view, _templates = _view(engine, PkTypesIntThing)

    async def _create(data):
        return PkTypesIntThing(name="x")

    view.adapter.create = _create  # type: ignore[method-assign]
    response = anyio.run(view.create_view, _request("POST", {"name": "x"}))

    assert response.headers["location"] == "/pktypesintthing-list"


def test_inline_secrets_kept_for_uuid_child_rows(engine):
    """
    Scenario: sensitive inline values kept for UUID children
      Given a UUID parent with a UUID child holding a stored api_token
      When  the child row is resubmitted with an empty api_token
      Then  the stored api_token is put back into the submitted row
      And   a row with a malformed or foreign key is left untouched
    """
    parent = PkTypesUuidParent()
    child = PkTypesUuidChild(parent_id=parent.id, api_token="s3cret")
    _seed(engine, parent)
    _seed(engine, child)
    spec = InlineModelSpec(
        model=PkTypesUuidChild,
        fk_field="parent_id",
        relationship_name="children",
        fields=["api_token"],
    )
    view, _templates = _view(engine, PkTypesUuidParent)
    formset = InlineFormset(spec=spec)

    async def _related(pk, field):
        return [child]

    view.adapter.get_related = _related  # type: ignore[method-assign]
    rows = [
        {"_pk": str(child.id).upper(), "api_token": ""},
        {"_pk": "not-a-uuid", "api_token": ""},
        {"_pk": str(uuid.uuid4()), "api_token": ""},
    ]

    anyio.run(view._keep_stored_inline_secrets, formset, rows, parent.id)

    assert [r["api_token"] for r in rows] == ["s3cret", "", ""]
