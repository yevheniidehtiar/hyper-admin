"""Pk-agnostic item links/testids and tz-aware datetime rendering (st-v058-byoa-45).

BYOA SDD section A.9: templates read a row's key through ``ha_pk`` (URLs) and
``ha_dom_token`` (DOM ids and ``data-testid`` values) instead of ``item.id``;
display cells use ``ha_display``; the ``datetime_input`` widget formats its
value with ``ha_datetime_input``, takes ``step="1"`` and shows a timezone hint.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.responses import Response

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth._types import UTCNaiveDateTime
from hyperadmin.core.actions import ActionDef, action
from hyperadmin.core.bulk_results import BulkRowResult
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.template_filters import ha_dom_token, register_template_filters

# ---------------------------------------------------------------------------
# Fixture models
# ---------------------------------------------------------------------------


class TplProduct(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = "product"


class TplDocument(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = "document"
    pages: int = 0


class TplCountry(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    code: str = Field(primary_key=True)
    name: str = "country"


class TplMeeting(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    title: str = "meeting"
    starts_at: datetime = Field(sa_type=UTCNaiveDateTime)  # type: ignore[call-overload]


class _Admin(ModelAdmin):
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


def _admin(engine: Any, *, timezone_name: str = "UTC") -> tuple[FastAPI, Admin]:
    app = FastAPI()
    settings = HyperAdminSettings(create_tables=False, timezone=timezone_name)
    return app, Admin(app=app, engine=engine, settings=settings)


def _mount(
    engine: Any,
    model: type[SQLModel],
    *,
    options: AdminOptions | None = None,
    timezone_name: str = "UTC",
) -> TestClient:
    app, admin = _admin(engine, timezone_name=timezone_name)
    site.register(model, _Admin, options=options or AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app)


def _href(html: str, testid: str) -> str:
    match = re.search(rf'href="([^"]+)"[^>]*data-testid="{testid}"', html)
    assert match, f"no link with data-testid={testid!r}"
    return match.group(1)


def _attr(html: str, attr: str, testid: str) -> str:
    match = re.search(rf'{attr}="([^"]+)"[^>]*\s+data-testid="{testid}"', html, re.DOTALL)
    assert match, f"no {attr} next to data-testid={testid!r}"
    return match.group(1)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_int_id_links_unchanged(engine) -> None:
    """
    Scenario: int-id links unchanged
      Given an int-id Product with id 7
      When  the list renders
      Then  the View href is /admin/product/7
      And   the edit testid is cell-edit-name-7
    """
    _seed(engine, TplProduct(id=7, name="widget"))
    client = _mount(engine, TplProduct, options=AdminOptions(list_editable=["name"]))

    html = client.get("/admin/tplproduct").text

    assert _href(html, "row-view-link").endswith("/admin/tplproduct/7")
    assert _href(html, "row-edit-link").endswith("/admin/tplproduct/7/edit")
    assert 'data-testid="cell-edit-name-7"' in html
    assert 'data-testid="cell-name-7"' in html
    assert 'id="cell-tplproduct-7-name"' in html
    assert 'aria-label="Edit name for row 7"' in html


def test_uuid_links_work(engine) -> None:
    """
    Scenario: UUID links work
      Given a UUID Document
      When  View, Edit and Delete are followed
      Then  each page returns 200
    """
    doc = TplDocument(name="spec")
    _seed(engine, doc)
    client = _mount(engine, TplDocument)
    html = client.get("/admin/tpldocument").text
    delete_url = _attr(html, "hx-delete", "row-delete-btn")

    view = client.get(_href(html, "row-view-link"))
    edit = client.get(_href(html, "row-edit-link"))
    delete = client.delete(delete_url)

    assert delete_url.endswith(f"/admin/tpldocument/{doc.id}")
    assert view.status_code == 200
    assert edit.status_code == 200
    assert f'hx-put="http://testserver/admin/tpldocument/{doc.id}"' in edit.text
    assert delete.status_code == 200


def test_aware_edit_value(engine) -> None:
    """
    Scenario: aware edit value
      Given an aware starts_at
      When  the edit form renders
      Then  the input value is display-tz ISO with seconds and step=1
      And   a timezone hint names the display timezone
    """
    _seed(
        engine,
        TplMeeting(id=1, starts_at=datetime(2026, 7, 1, 8, 0, 5, tzinfo=timezone.utc)),
    )
    client = _mount(engine, TplMeeting, timezone_name="Europe/Amsterdam")

    html = client.get("/admin/tplmeeting/1/edit").text

    tag = re.search(r'<input id="starts_at"[^>]*>', html, re.DOTALL)
    assert tag is not None
    assert 'value="2026-07-01T10:00:05"' in tag.group(0)
    assert 'step="1"' in tag.group(0)
    assert 'aria-describedby="starts_at-tz"' in tag.group(0)
    hint = re.search(r'data-testid="starts_at-tz">([^<]*)<', html)
    assert hint is not None
    assert "Europe/Amsterdam" in hint.group(1)


def test_aware_list_cell(engine) -> None:
    """
    Scenario: aware list cell
      Given an aware datetime column
      When  the list renders
      Then  a <time> element with a UTC ISO datetime attribute is shown
    """
    _seed(engine, TplMeeting(id=1, starts_at=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)))
    client = _mount(
        engine,
        TplMeeting,
        options=AdminOptions(list_display=["id", "starts_at"]),
        timezone_name="Europe/Amsterdam",
    )

    html = client.get("/admin/tplmeeting").text

    assert '<time datetime="2026-07-01T08:00:00+00:00">2026-07-01 10:00:00</time>' in html


# ---------------------------------------------------------------------------
# Natural keys: links percent-encode, DOM tokens hash
# ---------------------------------------------------------------------------


def test_natural_key_list_links_and_tokens(engine) -> None:
    """
    Scenario: a natural key with spaces gets working links and safe testids
      Given a Country whose key is 'a b?c' and name is list-editable
      When  the list renders and its View link is followed
      Then  the link percent-encodes the key and returns 200
      And   ids and testids use the hashed DOM token
      And   the pk column is never rendered as an inline-editable cell
    """
    _seed(engine, TplCountry(code="a b?c", name="Atlantis"))
    client = _mount(
        engine,
        TplCountry,
        options=AdminOptions(list_display=["code", "name"], list_editable=["code", "name"]),
    )
    token = ha_dom_token("a b?c")

    html = client.get("/admin/tplcountry").text
    view = client.get(_href(html, "row-view-link"))

    assert _href(html, "row-view-link").endswith("/admin/tplcountry/a%20b%3Fc")
    assert view.status_code == 200
    assert f'data-testid="cell-edit-name-{token}"' in html
    assert f'id="cell-tplcountry-{token}-name"' in html
    assert "cell-edit-code-" not in html


def test_natural_key_inline_editor_and_error(engine) -> None:
    """
    Scenario: inline editing fragments are keyed by the DOM token
      Given a Country whose key is 'a b?c' with a list-editable name
      When  the inline editor opens, is saved and is cancelled
      Then  the editor posts to the percent-encoded key
      And   its ids and testids use the hashed DOM token
    """
    _seed(engine, TplCountry(code="a b?c", name="Atlantis"))
    client = _mount(
        engine,
        TplCountry,
        options=AdminOptions(list_display=["code", "name"], list_editable=["name"]),
    )
    token = ha_dom_token("a b?c")

    editor = client.get("/admin/tplcountry/a%20b%3Fc/inline/name")
    saved = client.post("/admin/tplcountry/a%20b%3Fc/inline/name", data={"name": "Lemuria"})
    cancel = client.get("/admin/tplcountry/a%20b%3Fc/inline/name?cancel=1")

    assert editor.status_code == 200
    assert f'data-testid="cell-editor-name-{token}"' in editor.text
    assert f'id="inline-name-{token}"' in editor.text
    assert "/admin/tplcountry/a%20b%3Fc/inline/name" in editor.text
    assert saved.status_code == 200
    assert f'data-testid="cell-saved-flag-name-{token}"' in saved.text
    assert f'data-testid="cell-value-name-{token}"' in cancel.text


def test_inline_cell_error_keyed_by_uuid(engine) -> None:
    """
    Scenario: the inline error fragment is keyed by the row's UUID
      Given a UUID Document whose int 'pages' column is list-editable
      When  an invalid inline value is saved
      Then  the 422 fragment posts back to the UUID URL
      And   its ids and testids carry the UUID
    """
    doc = TplDocument(name="spec")
    _seed(engine, doc)
    client = _mount(engine, TplDocument, options=AdminOptions(list_editable=["pages"]))

    response = client.post(f"/admin/tpldocument/{doc.id}/inline/pages", data={"pages": "many"})

    assert response.status_code == 422
    assert f'data-testid="cell-editor-pages-{doc.id}"' in response.text
    assert f'data-testid="cell-cancel-pages-{doc.id}"' in response.text
    assert f'id="pages-errors-{doc.id}"' in response.text
    assert f"/admin/tpldocument/{doc.id}/inline/pages" in response.text


class _DocAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Ping")
    async def ping(self, request: Any, item_id: Any) -> Any:
        return None


def test_detail_action_posts_to_uuid_url(engine) -> None:
    """
    Scenario: a detail-page action button posts to the UUID URL
      Given a UUID Document with a 'ping' action
      When  the detail page renders
      Then  the action button posts to /admin/tpldocument/<uuid>/action/ping
    """
    doc = TplDocument(name="spec")
    _seed(engine, doc)
    app, admin = _admin(engine)
    site.register(TplDocument, _DocAdmin)
    admin.mount(path="/admin")

    html = TestClient(app).get(f"/admin/tpldocument/{doc.id}").text

    assert f'hx-post="http://testserver/admin/tpldocument/{doc.id}/action/ping"' in html


# ---------------------------------------------------------------------------
# Review amendments: bulk pages and inline formset rows
# ---------------------------------------------------------------------------


def _env(engine: Any) -> Environment:
    _app, admin = _admin(engine)
    admin.mount(path="/admin")
    return admin.templates.env


def test_bulk_result_status_testid_uses_dom_token(engine) -> None:
    """
    Scenario: a bulk result row with a natural key gets a safe testid
      Given bulk outcomes for the keys 7 and 'a b?c'
      When  bulk_result.html renders
      Then  the status testids are bulk-result-status-7 and the hashed token
      And   the retry form carries the failed keys as hidden ids
    """
    template = _env(engine).get_template("components/bulk_result.html")
    outcomes = [
        BulkRowResult(id=7, status="ok", detail=None),
        BulkRowResult(id="a b?c", status="failed", detail="boom"),
    ]

    html = template.render(
        action=SimpleNamespace(label="Archive"),
        outcomes=outcomes,
        bulk_endpoint_url="/bulk",
        failed_ids=["a b?c"],
    )

    assert 'data-testid="bulk-result-status-7"' in html
    assert f'data-testid="bulk-result-status-{ha_dom_token("a b?c")}"' in html
    assert '<input type="hidden" name="ids" value="a b?c" />' in html


def _bulk_view(engine: Any) -> tuple[DynamicModelView, MagicMock]:
    templates = MagicMock()
    templates.TemplateResponse.return_value = Response("ok")
    view = DynamicModelView(
        adapter=SQLModelAdapter(TplDocument, engine),
        options=AdminOptions(),
        templates=templates,
        app_label=None,
    )
    return view, templates


def _bulk_request() -> Any:
    return SimpleNamespace(url_for=lambda name, **params: f"/{name}")


def test_bulk_form_and_result_ids_are_canonical_strings(engine) -> None:
    """
    Scenario: bulk pages carry keys stringified with the model's pk codec
      Given a UUID model and a bulk action
      When  the bulk form and the bulk result render
      Then  the hidden ids are the canonical UUID strings
    """
    view, templates = _bulk_view(engine)
    key = uuid.UUID("12345678-1234-5678-1234-567812345678")
    act = ActionDef(name="archive", label="Archive", handler=MagicMock(), bulk=True)

    view._render_bulk_form(_bulk_request(), act, [key])
    form_ids = templates.TemplateResponse.call_args.args[2]["ids"]
    view._render_bulk_result(
        _bulk_request(), act, [BulkRowResult(id=key, status="failed", detail="x")]
    )
    failed_ids = templates.TemplateResponse.call_args.args[2]["failed_ids"]

    assert form_ids == [str(key)]
    assert failed_ids == [str(key)]


def test_bulk_form_hidden_ids(engine) -> None:
    """
    Scenario: the bulk parameter form preserves every selected key
      Given the selected keys '7' and 'a b?c'
      When  bulk_form.html renders
      Then  each key is a hidden 'ids' input
    """
    template = _env(engine).get_template("components/bulk_form.html")

    html = template.render(
        action=SimpleNamespace(label="Archive"), ids=["7", "a b?c"], fields=[], confirm_url="/c"
    )

    assert '<input type="hidden" name="ids" value="7" />' in html
    assert '<input type="hidden" name="ids" value="a b?c" />' in html


def _inline_row(pk: Any) -> SimpleNamespace:
    return SimpleNamespace(
        pk=pk, index=0, delete=False, has_errors=False, fields=[], pk_errors=None
    )


@pytest.mark.parametrize("pk", [0, ""], ids=["zero", "empty"])
def test_inline_row_keeps_falsy_pk(engine, pk: Any) -> None:
    """
    Scenario: a child row whose key is falsy keeps its hidden pk
      Given an inline formset row whose pk is 0 or ''
      When  inline_row.html renders
      Then  the hidden '<prefix>-<index>-pk' input is present
    """
    template = _env(engine).get_template("components/inline_row.html")

    html = template.render(row=_inline_row(pk), inline=SimpleNamespace(prefix="child"))

    assert f'name="child-0-pk" value="{pk}"' in html


def test_inline_row_without_pk_has_no_hidden_pk(engine) -> None:
    """
    Scenario: a new child row has no hidden pk
      Given an inline formset row whose pk is None
      When  inline_row.html renders
      Then  no hidden pk input is rendered
    """
    template = _env(engine).get_template("components/inline_row.html")

    html = template.render(row=_inline_row(None), inline=SimpleNamespace(prefix="child"))

    assert "child-0-pk" not in html


# ---------------------------------------------------------------------------
# Timezone hint
# ---------------------------------------------------------------------------


def test_timezone_hint_follows_the_request_override(engine) -> None:
    """
    Scenario: the datetime timezone hint follows a per-request override
      Given the admin timezone is UTC and a middleware sets Asia/Tokyo
      When  the edit form renders an aware starts_at of 08:00Z
      Then  the input shows 17:00:00 and the hint names Asia/Tokyo
    """
    _seed(engine, TplMeeting(id=1, starts_at=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)))
    client = _mount(engine, TplMeeting)

    @client.app.middleware("http")  # type: ignore[attr-defined]
    async def _tokyo(request, call_next):
        request.state.hyperadmin_timezone = "Asia/Tokyo"
        return await call_next(request)

    html = client.get("/admin/tplmeeting/1/edit").text

    assert 'value="2026-07-01T17:00:00"' in html
    assert re.search(r'data-testid="starts_at-tz">[^<]*Asia/Tokyo', html)


@pytest.mark.parametrize(
    ("default", "expected"),
    [(timezone.utc, "UTC"), (ZoneInfo("Europe/Amsterdam"), "Europe/Amsterdam")],
    ids=["utc", "iana"],
)
def test_ha_timezone_name(default: Any, expected: str) -> None:
    """
    Scenario: ha_timezone_name names the resolved display timezone
      Given a registered default timezone and no per-request override
      When  ha_timezone_name() renders
      Then  the zone's name is returned
    """
    env = Environment()
    register_template_filters(env, default_timezone=default)

    html = env.from_string("{{ ha_timezone_name() }}").render(request=None)

    assert html == expected
