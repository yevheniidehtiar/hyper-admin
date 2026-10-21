"""Detail-page panel routes: ``render_panel_view``, ``stream_panel_view`` and ``pdf_stream_panel``.

Spec: ``docs/specs/detail-panels.md``; story ``st-v056-dp-02``. Each test maps
to one BDD scenario and runs the real routes through ``Admin.mount()`` with a
stand-in auth backend, so permission, object-permission and the
``HyperAdminRoute`` error handling are all exercised.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel
from starlette.responses import HTMLResponse, Response, StreamingResponse

import hyperadmin
from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import PanelDef, panel
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.panels import PDFStreamPanel, pdf_stream_panel, pdf_stream_response
from hyperadmin.panels.pdf import _filename_param
from hyperadmin.views import dynamic as dynamic_module
from hyperadmin.views.dynamic import (
    _as_attachment,
    _discard_stream,
    _disposition_filename,
    _human_size,
)

PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)
JSON = {"accept": "application/json"}
HTMX = {"HX-Request": "true"}


class PanelOrder(SQLModel, table=True):
    __tablename__ = "test_panel_order"
    id: int | None = Field(default=None, primary_key=True)
    title: str
    paid: bool = False


class PanelFree(SQLModel, table=True):
    """A model without panels: no panel routes exist for it."""

    __tablename__ = "test_panel_free"
    id: int | None = Field(default=None, primary_key=True)
    name: str


ALL_PANELS = frozenset(
    {
        "view_panelorder",
        "view_panelfree",
        "view_panelorder_panel_summary",
        "view_panelorder_panel_document",
        "view_panelorder_panel_raw",
        "view_panelorder_panel_invoice",
        "view_panelorder_panel_invoice_missing",
        "view_panelorder_panel_paid_only",
        "view_panelorder_panel_history",
        "view_panelorder_panel_refused",
        "view_panelorder_panel_broken",
    }
)


@dataclass
class _User:
    id: int = 1
    username: str = "viewer"
    is_superuser: bool = False
    granted: frozenset[str] = field(default_factory=lambda: ALL_PANELS)


class _Backend:
    def __init__(self, user: _User) -> None:
        self.user = user

    async def get_current_user(self, request: Any) -> _User:
        return self.user

    async def authenticate(self, username: str, password: str) -> None:
        return None


class _Checker:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return user.is_superuser or codename in user.granted

    async def get_user_permissions(self, user: Any) -> set[str]:
        return set(user.granted)


class _DenyObjects:
    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return False


async def _summary(request: Request, obj: Any) -> Response:
    return HTMLResponse("<p>ok</p>")


async def _document(request: Request, obj: Any) -> Response:
    return StreamingResponse(
        iter([PDF_BYTES]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="order.pdf"',
            "Content-Length": "186368",
        },
    )


async def _raw(request: Request, obj: Any) -> Response:
    return StreamingResponse(iter([b"raw-bytes"]), media_type="application/octet-stream")


async def _refused(request: Request, obj: Any) -> Response:
    raise HTTPException(status_code=403, detail="handler says no")


async def _broken(request: Request, obj: Any) -> Any:
    return "not a response"


def _panels(pdf_path: Path) -> list[PanelDef]:
    return [
        PanelDef(slug="summary", label="Summary", handler=_summary),
        PanelDef(slug="document", label="Document", handler=_document, icon="file-text"),
        PanelDef(slug="raw", label="Raw", handler=_raw),
        pdf_stream_panel(slug="invoice", label="Invoice", path_resolver=lambda o: pdf_path),
        pdf_stream_panel(
            slug="invoice_missing",
            label="Missing invoice",
            path_resolver=lambda o: pdf_path.with_name("nope.pdf"),
        ),
        PanelDef(
            slug="paid_only", label="Paid only", handler=_summary, enabled=lambda o: bool(o.paid)
        ),
        PanelDef(slug="refused", label="Refused", handler=_refused),
        PanelDef(slug="broken", label="Broken", handler=_broken),
        PanelDef(slug="secret", label="Secret", handler=_summary),
    ]


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(PDF_BYTES)
    return path


def _seed(engine: Any) -> None:
    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(
                SQLModel.metadata.create_all,
                tables=[PanelOrder.__table__, PanelFree.__table__],
            )
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            session.add(PanelOrder(id=1, title="unpaid order", paid=False))
            session.add(PanelOrder(id=2, title="paid order", paid=True))
            session.add(PanelFree(id=1, name="free"))
            await session.commit()

    anyio.run(_setup)


def _client(
    pdf_path: Path,
    *,
    user: _User | None = None,
    auth: bool = True,
    object_checker: Any = None,
) -> TestClient:
    class OrderAdmin(ModelAdmin):
        adapter_class = SQLModelAdapter
        options = AdminOptions(panels=_panels(pdf_path), object_permission_checker=object_checker)

        @panel(label="History")
        async def history(self, request: Request, obj: Any) -> Response:
            return HTMLResponse(f"history of {obj.title} via {type(self).__name__}")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _seed(engine)
    app = FastAPI()
    settings = HyperAdminSettings(create_tables=False, secret_key="x" * 40)
    if auth:
        admin = Admin(
            app=app,
            engine=engine,
            settings=settings,
            auth_backend=_Backend(user or _User()),
            permission_checker=_Checker(),
        )
    else:
        admin = Admin(app=app, engine=engine, settings=settings)
    site.register(PanelOrder, OrderAdmin)
    site.register(PanelFree)
    admin.mount(path="/admin")
    return TestClient(app)


# ---------------------------------------------------------------------------
# render_panel_view
# ---------------------------------------------------------------------------


def test_render_panel_view_returns_404_for_unknown_slug(pdf_path: Path) -> None:
    """
    Scenario: render_panel_view returns 404 for unknown slug
      When  GET /admin/panelorder/1/panels/missing
      Then  response is 404 with detail "Unknown panel"
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/missing", headers=JSON)

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown panel"


def test_html_handler_fragment_is_returned_inline(pdf_path: Path) -> None:
    """
    Scenario: HTMLResponse handler returns fragment inline
      Given a panel handler returning HTMLResponse(content="<p>ok</p>")
      When  GET /admin/panelorder/1/panels/summary
      Then  response body is "<p>ok</p>" and content-type is text/html
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/summary", headers=HTMX)

    assert response.status_code == 200
    assert response.text == "<p>ok</p>"
    assert response.headers["content-type"].startswith("text/html")


def test_panels_render_without_any_auth_configured(pdf_path: Path) -> None:
    """
    Scenario: panels work in an admin with no auth (permission checks are no-ops)
      Given an Admin without auth_backend or permission_checker
      When  GET /admin/panelorder/1/panels/summary
      Then  the fragment is returned
    """
    response = _client(pdf_path, auth=False).get("/admin/panelorder/1/panels/summary")

    assert response.status_code == 200
    assert response.text == "<p>ok</p>"


def test_streaming_handler_returns_document_viewer(pdf_path: Path) -> None:
    """
    Scenario: StreamingResponse handler returns iframe wrapper
      Given a panel handler returning a StreamingResponse
      When  GET /admin/panelorder/1/panels/document
      Then  response body contains "<iframe" with src ending in "/panels/document/stream"
      And   the viewer shows the file name and size from the response headers
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/document", headers=HTMX)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<iframe" in response.text
    assert 'src="http://testserver/admin/panelorder/1/panels/document/stream"' in response.text
    assert 'data-testid="panel-pdf-viewer"' in response.text
    assert (
        'href="http://testserver/admin/panelorder/1/panels/document/stream?download=1"'
        in response.text
    )
    assert "order.pdf" in response.text
    assert "182 KB" in response.text
    assert PDF_BYTES.decode() not in response.text


def test_viewer_falls_back_to_panel_label_without_filename(pdf_path: Path) -> None:
    """
    Scenario: a stream without Content-Disposition is titled after the panel
      Given a StreamingResponse handler that sets no headers
      When  GET /admin/panelorder/1/panels/raw
      Then  the viewer names the document "Raw" and shows no size
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/raw", headers=HTMX)

    assert response.status_code == 200
    assert "<span>Raw</span>" in response.text
    assert "ha-caption" not in response.text


def test_class_level_panel_handler_is_bound_to_the_admin(pdf_path: Path) -> None:
    """
    Scenario: a @panel method receives the admin instance and the loaded record
      Given OrderAdmin.history decorated with @panel
      When  GET /admin/panelorder/2/panels/history
      Then  the handler ran as a bound method with the loaded order
    """
    response = _client(pdf_path).get("/admin/panelorder/2/panels/history")

    assert response.status_code == 200
    assert response.text == "history of paid order via OrderAdmin"


def test_handler_returning_non_response_raises_type_error(pdf_path: Path) -> None:
    """
    Scenario: handler returns non-Response
      Given a panel handler returning a str
      When  GET /admin/panelorder/1/panels/broken
      Then  TypeError is raised at request time
    """
    with pytest.raises(TypeError, match="panel 'broken' handler must return"):
        _client(pdf_path).get("/admin/panelorder/1/panels/broken")


def test_item_not_found_is_404_before_any_handler_runs(pdf_path: Path) -> None:
    """
    Scenario: item not found
      When  GET /admin/panelorder/999/panels/broken
      Then  response is 404 and the (broken) handler never ran
    """
    response = _client(pdf_path).get("/admin/panelorder/999/panels/broken", headers=JSON)

    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"


# ---------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------


def test_permission_codename_gates_panel_access(pdf_path: Path) -> None:
    """
    Scenario: permission codename gates panel access
      Given user lacks "view_panelorder_panel_secret"
      When  GET /admin/panelorder/1/panels/secret
      Then  response is 403 with the forbidden panel fragment retargeted to the panel
      And   a sibling panel still renders
    """
    client = _client(pdf_path)

    response = client.get("/admin/panelorder/1/panels/secret", headers=HTMX)

    assert response.status_code == 403
    assert 'data-testid="panel-forbidden"' in response.text
    assert "view_panelorder_panel_secret" in response.text
    assert response.headers["HX-Retarget"] == "this"
    assert response.headers["HX-Reswap"] == "innerHTML"
    assert client.get("/admin/panelorder/1/panels/summary", headers=HTMX).status_code == 200


def test_handler_raising_403_renders_the_forbidden_fragment(pdf_path: Path) -> None:
    """
    Scenario: panel handler raising HTTPException(403) surfaces a forbidden body
      Given a panel handler that raises HTTPException(403)
      When  GET /admin/panelorder/1/panels/refused
      Then  the panel body is the forbidden fragment with status 403
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/refused", headers=HTMX)

    assert response.status_code == 403
    assert 'data-testid="panel-forbidden"' in response.text
    assert "view_panelorder_panel_refused" in response.text


def test_model_view_permission_is_required_for_panels(pdf_path: Path) -> None:
    """
    Scenario: a panel is part of the detail page
      Given a user holding the panel codename but not "view_panelorder"
      When  GET /admin/panelorder/1/panels/summary
      Then  response is 403
    """
    user = _User(granted=frozenset({"view_panelorder_panel_summary"}))

    response = _client(pdf_path, user=user).get("/admin/panelorder/1/panels/summary")

    assert response.status_code == 403
    assert 'data-testid="panel-forbidden"' in response.text


def test_object_permission_denied_renders_the_forbidden_fragment(pdf_path: Path) -> None:
    """
    Scenario: the object "view" check runs before the handler
      Given an object permission checker that denies every object
      When  GET /admin/panelorder/1/panels/summary
      Then  response is 403 with the forbidden fragment
    """
    client = _client(pdf_path, object_checker=_DenyObjects())

    response = client.get("/admin/panelorder/1/panels/summary", headers=HTMX)

    assert response.status_code == 403
    assert 'data-testid="panel-forbidden"' in response.text


def test_stream_panel_view_403_propagates_to_the_route(pdf_path: Path) -> None:
    """
    Scenario: the stream route re-checks permission and does not render a fragment
      Given user lacks "view_panelorder_panel_secret"
      When  GET /admin/panelorder/1/panels/secret/stream
      Then  response is a plain 403
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/secret/stream", headers=JSON)

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


def test_enabled_predicate_hides_the_panel_for_the_wrong_instance(pdf_path: Path) -> None:
    """
    Scenario: enabled(obj) returns False
      Given a panel enabled only for paid orders
      When  GET /admin/panelorder/1/panels/paid_only (unpaid)
      Then  response is 404
      And   GET /admin/panelorder/2/panels/paid_only (paid) is 200
    """
    client = _client(pdf_path)

    hidden = client.get("/admin/panelorder/1/panels/paid_only", headers=JSON)
    shown = client.get("/admin/panelorder/2/panels/paid_only")

    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Unknown panel"
    assert shown.status_code == 200


# ---------------------------------------------------------------------------
# stream_panel_view
# ---------------------------------------------------------------------------


def test_stream_panel_view_streams_bytes_with_inline_disposition(pdf_path: Path) -> None:
    """
    Scenario: stream_panel_view streams the bytes with inline disposition
      Given the streaming handler
      When  GET /admin/panelorder/1/panels/document/stream
      Then  response Content-Disposition is inline and body bytes equal the handler's stream
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/document/stream")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'inline; filename="order.pdf"'
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == PDF_BYTES


def test_stream_panel_view_defaults_disposition_to_inline(pdf_path: Path) -> None:
    """
    Scenario: a handler that sets no disposition still streams inline
      When  GET /admin/panelorder/1/panels/raw/stream
      Then  Content-Disposition is "inline"
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/raw/stream")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "inline"
    assert response.content == b"raw-bytes"


def test_download_query_turns_the_stream_into_an_attachment(pdf_path: Path) -> None:
    """
    Scenario: the viewer's Download button
      When  GET /admin/panelorder/1/panels/document/stream?download=1
      Then  Content-Disposition is "attachment" keeping the file name
      And   a headerless stream becomes a bare "attachment"
    """
    client = _client(pdf_path)

    named = client.get("/admin/panelorder/1/panels/document/stream?download=1")
    bare = client.get("/admin/panelorder/1/panels/raw/stream?download")

    assert named.headers["content-disposition"] == 'attachment; filename="order.pdf"'
    assert bare.headers["content-disposition"] == "attachment"


# ---------------------------------------------------------------------------
# detail page context and route registration
# ---------------------------------------------------------------------------


def test_detail_page_lists_visible_panels_with_urls(pdf_path: Path) -> None:
    """
    Scenario: detail page renders configured panel tabs
      Given panels with enabled predicates and per-panel permissions
      When  the user opens /admin/panelorder/1
      Then  the template context lists the enabled, permitted panels in declared order
      And   each carries the URL of its render route
    """
    response = _client(pdf_path).get("/admin/panelorder/1")

    assert response.status_code == 200
    panels = response.context["panels"]
    assert [p["slug"] for p in panels] == [
        "summary",
        "document",
        "raw",
        "invoice",
        "invoice_missing",
        "refused",
        "broken",
        "history",
    ]
    assert panels[0] == {
        "slug": "summary",
        "label": "Summary",
        "icon": None,
        "url": "http://testserver/admin/panelorder/1/panels/summary",
    }
    assert panels[1]["icon"] == "file-text"


def test_detail_page_includes_predicate_panel_when_enabled(pdf_path: Path) -> None:
    """
    Scenario: the tab appears for an instance the predicate accepts
      When  the user opens /admin/panelorder/2 (paid)
      Then  "paid_only" is among the listed panels and "secret" still is not
    """
    response = _client(pdf_path).get("/admin/panelorder/2")

    slugs = [p["slug"] for p in response.context["panels"]]
    assert "paid_only" in slugs
    assert "secret" not in slugs


def test_models_without_panels_get_no_panel_routes(pdf_path: Path) -> None:
    """
    Scenario: no panels, no routes
      Given a model registered without panels
      When  GET /admin/panelfree/1/panels/anything
      Then  response is 404 (no such route) and the detail page lists no panels
    """
    client = _client(pdf_path)

    assert client.get("/admin/panelfree/1/panels/anything", headers=JSON).status_code == 404
    assert client.get("/admin/panelfree/1").context["panels"] == []


def test_duplicate_panel_slug_raises_at_mount() -> None:
    """
    Scenario: panel slug collision raises at registration
      Given AdminOptions(panels=[PanelDef(slug="x")]) and a @panel method with slug "x"
      When  the admin is mounted
      Then  ValueError "duplicate panel slug 'x'" is raised
    """

    class DupAdmin(ModelAdmin):
        adapter_class = SQLModelAdapter
        options = AdminOptions(panels=[PanelDef(slug="x", label="A", handler=_summary)])

        @panel(label="B", slug="x")
        async def x_again(self, request: Request, obj: Any) -> Response:
            return HTMLResponse("B")

    admin = Admin(
        app=FastAPI(),
        engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
        settings=HyperAdminSettings(create_tables=False),
    )
    site.register(PanelOrder, DupAdmin)

    with pytest.raises(ValueError, match="duplicate panel slug 'x'"):
        admin.mount(path="/admin")


# ---------------------------------------------------------------------------
# pdf_stream_panel factory
# ---------------------------------------------------------------------------


def test_pdf_stream_panel_returns_a_panel_def() -> None:
    """
    Scenario: pdf_stream_panel factory in hyperadmin.panels returns a PanelDef
      Given the keyword arguments of the spec
      Then  a PanelDef carrying them is returned, and PDFStreamPanel is the same factory
    """
    enabled = lambda o: True  # noqa: E731 - identity matters in the assertion

    pd = pdf_stream_panel(
        slug="invoice",
        label="Invoice",
        path_resolver=lambda o: Path("/x.pdf"),
        enabled=enabled,
        icon="file-text",
        permission="custom_codename",
    )

    assert isinstance(pd, PanelDef)
    assert (pd.slug, pd.label, pd.icon, pd.permission) == (
        "invoice",
        "Invoice",
        "file-text",
        "custom_codename",
    )
    assert pd.enabled is enabled
    assert PDFStreamPanel is pdf_stream_panel
    assert hyperadmin.pdf_stream_panel is pdf_stream_panel
    assert hyperadmin.PDFStreamPanel is pdf_stream_panel


def test_pdf_stream_panel_streams_the_file_inline(pdf_path: Path) -> None:
    """
    Scenario: streaming panel returns Content-Disposition inline
      Given a pdf_stream_panel resolving to a PDF on disk
      When  GET /admin/panelorder/1/panels/invoice/stream
      Then  the PDF bytes are streamed as application/pdf, inline, with security headers
      And   the render route wraps it in the viewer with the file's name and size
    """
    client = _client(pdf_path)

    stream = client.get("/admin/panelorder/1/panels/invoice/stream")
    viewer = client.get("/admin/panelorder/1/panels/invoice", headers=HTMX)

    assert stream.status_code == 200
    assert stream.content == PDF_BYTES
    assert stream.headers["content-type"] == "application/pdf"
    assert stream.headers["content-disposition"] == 'inline; filename="invoice.pdf"'
    assert stream.headers["content-length"] == str(len(PDF_BYTES))
    assert stream.headers["x-content-type-options"] == "nosniff"
    assert stream.headers["cache-control"] == "private, no-store"
    assert "invoice.pdf" in viewer.text
    assert f"{len(PDF_BYTES)} B" in viewer.text


def test_pdf_stream_panel_returns_404_when_the_file_is_missing(pdf_path: Path) -> None:
    """
    Scenario: the resolved path is not a file
      When  GET /admin/panelorder/1/panels/invoice_missing
      Then  response is 404 "Document not found", not a 500
    """
    response = _client(pdf_path).get("/admin/panelorder/1/panels/invoice_missing", headers=JSON)

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_pdf_stream_response_stats_the_file_and_encodes_odd_names(pdf_path: Path) -> None:
    """
    Scenario: pdf_stream_response used directly by a consumer handler
      Given no explicit size and a non-ASCII file name
      Then  Content-Length comes from a stat and the name uses RFC 5987 encoding
    """
    response = pdf_stream_response(pdf_path, filename="facture é.pdf")

    assert response.headers["content-length"] == str(len(PDF_BYTES))
    assert (
        response.headers["content-disposition"] == "inline; filename*=utf-8''facture%20%C3%A9.pdf"
    )
    assert _filename_param('we"ird.pdf') == "filename*=utf-8''we%22ird.pdf"
    assert _filename_param("plain.pdf") == 'filename="plain.pdf"'


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("", None),
        ("inline", None),
        ('inline; filename="order.pdf"', "order.pdf"),
        ("attachment; filename=order.pdf", "order.pdf"),
        ("inline; filename*=utf-8''facture%20%C3%A9.pdf", "facture é.pdf"),
        ("inline; filename*=UTF-8''a.pdf; foo=bar", "a.pdf"),
    ],
)
def test_disposition_filename(header: str | None, expected: str | None) -> None:
    assert _disposition_filename(header) == expected


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (None, None),
        ("abc", None),
        ("0", "0 B"),
        ("512", "512 B"),
        ("186368", "182 KB"),
        (str(5 * 1024 * 1024), "5 MB"),
        (str(2**40), "1 TB"),
        (str(2**50), "1024 TB"),
    ],
)
def test_human_size(length: str | None, expected: str | None) -> None:
    assert _human_size(length) == expected


@pytest.mark.parametrize(
    ("disposition", "expected"),
    [
        ("", "attachment"),
        ("inline", "attachment"),
        ('inline; filename="a.pdf"', 'attachment; filename="a.pdf"'),
        ('Attachment; filename="a.pdf"', 'Attachment; filename="a.pdf"'),
    ],
)
def test_as_attachment(disposition: str, expected: str) -> None:
    assert _as_attachment(disposition) == expected


@pytest.mark.anyio
async def test_discard_stream_closes_an_async_generator_body() -> None:
    """
    Scenario: the render route never sends a streaming body
      Given a StreamingResponse over an async generator
      When  the stream is discarded
      Then  the generator is closed and yields nothing afterwards
    """

    async def chunks() -> AsyncIterator[bytes]:
        yield b"x"

    response = StreamingResponse(chunks())

    await _discard_stream(response)

    with pytest.raises(StopAsyncIteration):
        await response.body_iterator.__anext__()


@pytest.mark.anyio
async def test_discard_stream_tolerates_iterators_without_aclose() -> None:
    """
    Scenario: a body iterator that is a plain async iterator
      When  the stream is discarded
      Then  nothing is called and no error is raised
    """

    class _Plain:
        def __aiter__(self) -> _Plain:
            return self

        async def __anext__(self) -> bytes:
            raise StopAsyncIteration

    response = StreamingResponse(_Plain())

    await _discard_stream(response)


def test_module_exports_streaming_response_type() -> None:
    """``render_panel_view`` detects streams by the starlette type, not a subclass of its own."""
    assert dynamic_module.StreamingResponse is StreamingResponse
