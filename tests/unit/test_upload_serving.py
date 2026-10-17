"""Per-record file serving behind permission, queryset and object checks (BYOA SDD C.5).

Story: ``.meta/epics/epic-v058-bring-your-own-app/stories/
fixuploads-serve-uploads-under-the-admin-prefix-behind-auth.md`` (st-v058-byoa-37).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType
from sqlalchemy import Column, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import HyperAdminRouter
from hyperadmin.views.uploads import download_name, unique_upload_name

if TYPE_CHECKING:
    from collections.abc import Iterator

_STORAGE_ROOT = tempfile.mkdtemp(prefix="hyperadmin-serve-")
_storage = FileSystemStorage(_STORAGE_ROOT)


# ---------------------------------------------------------------------------
# Models and admins
# ---------------------------------------------------------------------------


class SrvDocument(SQLModel, table=True):
    __tablename__ = "serve_document"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    tenant: str = "A"
    doc: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))


class SrvSecret(SQLModel, table=True):
    __tablename__ = "serve_secret"

    id: int | None = Field(default=None, primary_key=True)
    doc: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))


class SrvDocumentAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        tenant = getattr(request.state, "tenant", None) if request is not None else None
        return {"tenant": tenant} if tenant else {}


class SrvSecretAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


ALL_PERMS = frozenset(
    f"{verb}_{model}"
    for verb in ("view", "add", "change", "delete")
    for model in ("srvdocument", "srvsecret")
)


class _User:
    def __init__(self, perms: frozenset[str] | set[str] = ALL_PERMS) -> None:
        self.perms = frozenset(perms)
        self.is_superuser = False


class _PermChecker:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return codename in user.perms


class _DenyObject:
    """Object permission checker that denies ``view`` on document 2."""

    async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
        return not (getattr(obj, "id", None) == 2 and action == "view")


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
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(name: str, content: bytes) -> str:
    target = Path(_STORAGE_ROOT) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return name


async def _seed(engine: AsyncEngine, docs: dict[int, str | None]) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for doc_id, name in docs.items():
            await conn.execute(
                text(
                    "INSERT INTO serve_document (id, title, tenant, doc) VALUES (:i, 't', :t, :d)"
                ),
                {"i": doc_id, "t": "B" if doc_id == 3 else "A", "d": name},
            )
        secret_doc = next(iter(docs.values()), None)
        await conn.execute(
            text("INSERT INTO serve_secret (id, doc) VALUES (1, :d)"), {"d": secret_doc}
        )


def _client(
    docs: dict[int, str | None],
    user: Any = None,
    *,
    tenant: str | None = None,
    storage: Any = _storage,
    document_options: AdminOptions | None = None,
    **settings: Any,
) -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine, docs)
    app = FastAPI()

    @app.middleware("http")
    async def _attach(request: Request, call_next: Any) -> Any:
        request.state.user = user or _User()
        request.state.tenant = tenant
        return await call_next(request)

    admin = _PermAdmin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, **settings),
        permission_checker=_PermChecker(),
        storage=storage,
    )
    # A fresh subclass per app: registering options must not leak between tests.
    document_admin = type("SrvDocumentTestAdmin", (SrvDocumentAdmin,), {})
    site.register(SrvDocument, document_admin, options=document_options)
    site.register(SrvSecret, SrvSecretAdmin)
    admin.mount(path="/admin")
    return TestClient(app), engine


def _doc_names(engine: AsyncEngine) -> list[str]:
    async def _run() -> list[str]:
        async with engine.connect() as conn:
            rows = await conn.execute(text("SELECT doc FROM serve_document ORDER BY id"))
            return [r[0] for r in rows]

    return anyio.run(_run)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_uploads_require_authentication(tmp_path: Path) -> None:
    """
    Scenario: uploads require authentication
      Given auth enabled and a document with a stored file
      When  an anonymous GET /admin/srvdocument/1/file/doc is made
      Then  it redirects to /admin/login
    """
    # Given
    name = _store("auth-a.pdf", b"%PDF")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key="test-secret-key"),
        storage=_storage,
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )
    site.register(SrvDocument, SrvDocumentAdmin)
    admin.mount("/admin")
    anyio.run(_seed, engine, {1: name})

    # When
    resp = TestClient(app).get("/admin/srvdocument/1/file/doc", follow_redirects=False)

    # Then
    assert resp.status_code in (302, 303, 307)
    assert resp.headers["location"].endswith("/admin/login")


def test_files_are_not_served_at_the_host_root() -> None:
    """
    Scenario: not served at root
      Given file storage configured and a stored a.pdf
      When  GET /uploads/a.pdf is requested
      Then  the status is 404
    """
    # Given
    name = _store("a.pdf", b"%PDF")
    client, _ = _client({1: name})

    # When
    resp = client.get(f"/uploads/{name}")

    # Then
    assert resp.status_code == 404


def test_svg_is_downloaded_as_an_attachment() -> None:
    """
    Scenario: SVG downloaded
      Given an authenticated user and a document holding x.svg
      When  GET /admin/srvdocument/1/file/doc is requested
      Then  Content-Disposition is attachment
      And   nosniff and a sandbox CSP are set
      And   the browser is told not to store the file
    """
    # Given
    name = _store("x.svg", b"<svg onload='alert(1)'/>")
    client, _ = _client({1: name})

    # When
    resp = client.get("/admin/srvdocument/1/file/doc")

    # Then
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["content-security-policy"] == "sandbox"
    assert resp.headers["cache-control"] == "private, no-store"
    assert not resp.headers["content-type"].startswith("image/svg")
    assert resp.content == b"<svg onload='alert(1)'/>"


def test_allow_listed_raster_image_is_served_inline() -> None:
    """
    Scenario: raster image shown inline
      Given an authenticated user and a document holding photo.PNG
      When  GET /admin/srvdocument/1/file/doc is requested
      Then  Content-Disposition is inline with an image/png type
      And   nosniff is still set
      And   the browser is told not to store the file
    """
    # Given
    name = _store("photo.PNG", b"\x89PNG")
    client, _ = _client({1: name})

    # When
    resp = client.get("/admin/srvdocument/1/file/doc")

    # Then
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].startswith("inline")
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "private, no-store"


def test_stored_name_outside_the_storage_root_is_rejected() -> None:
    """
    Scenario: traversal rejected
      Given an authenticated user and a record whose file column holds ../../etc/passwd
      When  GET /admin/srvdocument/1/file/doc is requested
      Then  the status is 404
    """
    # Given
    client, _ = _client({1: "../../../../../../etc/passwd"})

    # When
    resp = client.get("/admin/srvdocument/1/file/doc")

    # Then
    assert resp.status_code == 404


def test_traversal_in_the_field_segment_is_rejected() -> None:
    """
    Scenario: traversal in the URL rejected
      Given an authenticated user
      When  GET /admin/srvdocument/1/file/..%2F..%2Fetc%2Fpasswd is requested
      Then  the status is 404
    """
    # Given
    client, _ = _client({1: _store("t.pdf", b"x")})

    # When
    resp = client.get("/admin/srvdocument/1/file/..%2F..%2Fetc%2Fpasswd")

    # Then
    assert resp.status_code == 404


def test_symlink_escaping_the_storage_root_is_rejected(tmp_path: Path) -> None:
    """
    Scenario: symlinked escape rejected
      Given a stored name that follows a symlink out of the storage root
      When  the file is requested
      Then  the status is 404 and the outside file is not disclosed
    """
    # Given
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TOP SECRET")
    link = Path(_STORAGE_ROOT) / f"escape-{tmp_path.name}"
    link.symlink_to(outside, target_is_directory=True)
    client, _ = _client({1: f"{link.name}/secret.txt"})

    # When
    try:
        resp = client.get("/admin/srvdocument/1/file/doc")
    finally:
        link.unlink()

    # Then
    assert resp.status_code == 404
    assert "TOP SECRET" not in resp.text


def test_cross_model_read_is_denied() -> None:
    """
    Scenario: cross-model read denied
      Given a user with view on SrvDocument only
      When  GET /admin/srvsecret/1/file/doc is requested
      Then  the status is 403
    """
    # Given
    name = _store("cross.pdf", b"secret")
    client, _ = _client({1: name}, _User({"view_srvdocument"}))

    # When
    resp = client.get("/admin/srvsecret/1/file/doc")
    own = client.get("/admin/srvdocument/1/file/doc")

    # Then
    assert resp.status_code == 403
    assert own.status_code == 200


def test_same_name_upload_does_not_overwrite_another_records_file() -> None:
    """
    Scenario: a same-name upload does not overwrite
      Given a document created with report.txt containing "first"
      When  a second document is created with another report.txt
      Then  both records keep their own file contents
    """
    # Given
    client, engine = _client({})
    first = client.post(
        "/admin/srvdocument",
        data={"title": "one", "tenant": "A"},
        files={"doc": ("report.txt", b"first", "text/plain")},
        follow_redirects=False,
    )

    # When
    second = client.post(
        "/admin/srvdocument",
        data={"title": "two", "tenant": "A"},
        files={"doc": ("report.txt", b"second", "text/plain")},
        follow_redirects=False,
    )

    # Then
    assert first.status_code == 303
    assert second.status_code == 303
    names = _doc_names(engine)
    assert len(set(names)) == 2
    assert all(n.endswith("report.txt") for n in names)
    assert [(Path(_STORAGE_ROOT) / n).read_bytes() for n in names] == [b"first", b"second"]
    download = client.get("/admin/srvdocument/1/file/doc")
    assert download.content == b"first"
    assert 'filename="report.txt"' in download.headers["content-disposition"]


# ---------------------------------------------------------------------------
# Supporting behaviour
# ---------------------------------------------------------------------------


def test_record_outside_the_queryset_scope_is_not_served() -> None:
    """
    Scenario: another tenant's file is hidden
      Given get_queryset scopes the user to tenant A and document 3 belongs to tenant B
      When  GET /admin/srvdocument/3/file/doc is requested
      Then  the status is 404
    """
    # Given
    name = _store("tenant-b.pdf", b"B only")
    client, _ = _client({1: name, 3: name}, tenant="A")

    # When
    resp = client.get("/admin/srvdocument/3/file/doc")

    # Then
    assert resp.status_code == 404
    assert client.get("/admin/srvdocument/1/file/doc").status_code == 200


def test_object_view_check_applies_to_file_downloads() -> None:
    """
    Scenario: object view check denies the file
      Given an object checker that denies view on document 2
      When  GET /admin/srvdocument/2/file/doc is requested
      Then  the status is 403
    """
    # Given
    name = _store("obj.pdf", b"x")
    client, _ = _client(
        {1: name, 2: name}, document_options=AdminOptions(object_permission_checker=_DenyObject())
    )

    # When
    resp = client.get("/admin/srvdocument/2/file/doc")

    # Then
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("docs", "path"),
    [
        ({1: "present.pdf"}, "/admin/srvdocument/1/file/title"),
        ({1: None}, "/admin/srvdocument/1/file/doc"),
        ({1: "missing-on-disk.pdf"}, "/admin/srvdocument/1/file/doc"),
        ({1: "present.pdf"}, "/admin/srvdocument/9/file/doc"),
    ],
    ids=["not-a-file-field", "empty-value", "missing-file", "missing-record"],
)
def test_unservable_file_requests_return_404(docs: dict[int, str | None], path: str) -> None:
    """
    Scenario: nothing to serve
      Given a non-file field, an empty value, a missing file or a missing record
      When  the file route is requested
      Then  the status is 404
    """
    # Given
    _store("present.pdf", b"x")
    client, _ = _client(docs)

    # When
    resp = client.get(path)

    # Then
    assert resp.status_code == 404


def test_sensitive_file_field_is_not_served() -> None:
    """
    Scenario: sensitive file field hidden
      Given the doc field is marked sensitive
      When  GET /admin/srvdocument/1/file/doc is requested
      Then  the status is 404
    """
    # Given
    name = _store("sensitive.pdf", b"x")
    client, _ = _client({1: name}, document_options=AdminOptions(sensitive_fields={"doc": True}))

    # When
    resp = client.get("/admin/srvdocument/1/file/doc")

    # Then
    assert resp.status_code == 404


def test_detail_page_links_to_the_per_record_route() -> None:
    """
    Scenario: detail page download link
      Given a document with a stored file
      When  its detail page is rendered
      Then  the download link points at /admin/srvdocument/1/file/doc
    """
    # Given
    name = _store("linked.pdf", b"x")
    client, _ = _client({1: name})

    # When
    resp = client.get("/admin/srvdocument/1")

    # Then
    assert resp.status_code == 200
    assert 'href="http://testserver/admin/srvdocument/1/file/doc"' in resp.text
    assert "/uploads/" not in resp.text


def test_detail_page_link_text_hides_the_unique_upload_prefix() -> None:
    """
    Scenario: download link shows the original file name
      Given a document whose stored file name carries a unique upload prefix
      When  its detail page is rendered
      Then  the download link text is the original file name
      And   the prefixed stored name is not shown
    """
    # Given
    stored = f"{'ab' * 16}-report.pdf"
    name = _store(stored, b"x")
    client, _ = _client({1: name})

    # When
    resp = client.get("/admin/srvdocument/1")

    # Then
    assert resp.status_code == 200
    assert 'data-testid="doc-download">report.pdf</a>' in resp.text
    assert stored not in resp.text


def test_detail_page_without_storage_shows_the_name_without_a_link() -> None:
    """
    Scenario: no storage, no link
      Given an admin without storage and a document holding a file name
      When  its detail page is rendered
      Then  the name is shown and no download link is rendered
    """
    # Given
    client, _ = _client({1: "plain.pdf"}, storage=None)

    # When
    resp = client.get("/admin/srvdocument/1")

    # Then
    assert resp.status_code == 200
    assert "plain.pdf" in resp.text
    assert 'data-testid="doc-download"' not in resp.text


def test_public_uploads_path_restores_the_legacy_mount(caplog: pytest.LogCaptureFixture) -> None:
    """
    Scenario: public_uploads_path escape hatch
      Given settings.public_uploads_path = "/uploads"
      When  GET /uploads/legacy.pdf is requested
      Then  the file is served publicly
      And   a startup warning names the setting
    """
    # Given
    name = _store("legacy.pdf", b"legacy")
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        client, _ = _client({1: name}, public_uploads_path="/uploads")

    # When
    resp = client.get(f"/uploads/{name}")

    # Then
    assert resp.status_code == 200
    assert resp.content == b"legacy"
    assert any("public_uploads_path" in r.getMessage() for r in caplog.records)


def test_public_uploads_path_is_ignored_for_storage_without_a_directory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: escape hatch needs a local directory
      Given a storage without a filesystem root and public_uploads_path set
      When  the admin is mounted
      Then  nothing is mounted at the public path and a warning is logged
    """

    # Given
    class _RemoteStorage:
        def write(self, file: Any, name: str) -> str:
            return name

    # When
    with caplog.at_level(logging.WARNING, logger="hyperadmin"):
        client, _ = _client({1: None}, storage=_RemoteStorage(), public_uploads_path="/media")

    # Then
    assert client.get("/media/anything.pdf").status_code == 404
    assert any("ignored" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("value", ["/", "uploads", "/uploads/", "/up loads"])
def test_public_uploads_path_must_be_an_absolute_non_root_path(value: str) -> None:
    """
    Scenario: invalid escape-hatch path rejected
      Given a public_uploads_path that is relative, the root or has a trailing slash
      When  the settings are built
      Then  validation fails
    """
    # Given / When / Then
    with pytest.raises(ValueError, match="public_uploads_path"):
        HyperAdminSettings(public_uploads_path=value)


def test_unique_upload_name_and_download_name_round_trip() -> None:
    """
    Scenario: the unique prefix is hidden from the download name
      Given a client file name with directory parts
      When  a unique stored name is generated for it
      Then  it is flat, prefixed and downloads under the original basename
    """
    # Given
    client_name = "..\\evil/../report.pdf"

    # When
    stored = unique_upload_name(_storage, client_name)

    # Then
    assert "/" not in stored
    assert stored.endswith("-report.pdf")
    assert download_name(stored) == "report.pdf"
    assert download_name("nested/plain.pdf") == "plain.pdf"
    assert len(unique_upload_name(None, ".hidden")) > 32
    assert len(unique_upload_name(None, "...")) == 32
