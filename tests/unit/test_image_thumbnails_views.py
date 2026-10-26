"""Thumbnails in the list, detail and update views (story #409, epic #410).

The thumbnails come from :func:`hyperadmin.uploads.generate_thumbnail`, served by
the per-record file route as ``?thumb=list`` (40x40) and ``?thumb=detail`` (200x200).
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from PIL import Image
from sqlalchemy import Column, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.routing import HyperAdminRouter
from hyperadmin.uploads.images import PLACEHOLDER_THUMBNAIL

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT = tempfile.mkdtemp(prefix="hyperadmin-thumbs-")
_storage = FileSystemStorage(_ROOT)


class ThumbPhoto(SQLModel, table=True):
    __tablename__ = "thumb_photo"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    photo: str | None = Field(default=None, sa_column=Column(ImageType(storage=_storage)))
    attachment: str | None = Field(default=None, sa_column=Column(FileType(storage=_storage)))


class ThumbPhotoAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class _User:
    is_superuser = True


class _AllowAll:
    async def has_permission(self, user: Any, codename: str) -> bool:
        return True


class _PermAdmin(Admin):
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


def _image(name: str, size: tuple[int, int] = (400, 300)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, format="JPEG")
    (Path(_ROOT) / name).write_bytes(buf.getvalue())
    return name


async def _seed(engine: AsyncEngine, photo: str | None, attachment: str | None) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(
            text("INSERT INTO thumb_photo (id, title, photo, attachment) VALUES (1, 't', :p, :a)"),
            {"p": photo, "a": attachment},
        )


def _client(photo: str | None, attachment: str | None = None) -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine, photo, attachment)
    app = FastAPI()

    @app.middleware("http")
    async def _attach(request: Any, call_next: Any) -> Any:
        request.state.user = _User()
        return await call_next(request)

    admin = _PermAdmin(
        app=app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False),
        permission_checker=_AllowAll(),
        storage=_storage,
    )
    site.register(ThumbPhoto, ThumbPhotoAdmin, options=AdminOptions(column_list=["id", "photo"]))
    admin.mount(path="/admin")
    return TestClient(app)


def test_thumbnail_variants_are_served_at_their_size() -> None:
    """
    Scenario: the file route serves resized thumbnails
      Given a record with a 400x300 stored image
      When  the file route is requested with thumb=list and thumb=detail
      Then  the images fit 40x40 and 200x200 and are served inline
    """
    # Given
    client = _client(_image("serve-a.jpg"))

    # When
    small = client.get("/admin/thumbphoto/1/file/photo?thumb=list")
    medium = client.get("/admin/thumbphoto/1/file/photo?thumb=detail")

    # Then
    assert small.status_code == 200
    assert small.headers["content-disposition"].startswith("inline")
    assert Image.open(io.BytesIO(small.content)).size == (40, 30)
    assert Image.open(io.BytesIO(medium.content)).size == (200, 150)


def test_unknown_thumbnail_variant_is_rejected() -> None:
    """
    Scenario: unknown variant
      Given a record with a stored image
      When  thumb=huge is requested
      Then  the status is 422
    """
    client = _client(_image("serve-b.jpg"))

    assert client.get("/admin/thumbphoto/1/file/photo?thumb=huge").status_code == 422


def test_thumbnail_of_non_image_field_is_404() -> None:
    """
    Scenario: no thumbnail for a plain file column
      Given a record whose attachment column holds a PDF
      When  thumb=list is requested for it
      Then  the status is 404 and the plain download still works
    """
    (Path(_ROOT) / "doc.pdf").write_bytes(b"%PDF")
    client = _client(None, "doc.pdf")

    assert client.get("/admin/thumbphoto/1/file/attachment?thumb=list").status_code == 404
    assert client.get("/admin/thumbphoto/1/file/attachment").status_code == 200


def test_failed_thumbnail_generation_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Scenario: thumbnail generation fails
      Given generate_thumbnail falls back to its placeholder
      When  thumb=list is requested
      Then  the status is 404 so the page can show a file icon
    """
    monkeypatch.setattr(
        "hyperadmin.views.dynamic.files.generate_thumbnail",
        lambda *_a, **_k: PLACEHOLDER_THUMBNAIL,
    )
    client = _client(_image("serve-c.jpg"))

    assert client.get("/admin/thumbphoto/1/file/photo?thumb=list").status_code == 404


def test_list_view_shows_a_lazy_thumbnail_per_image_cell() -> None:
    """
    Scenario: list view shows 40x40 thumbnail for image column
      Given a record with a stored image
      When  the list view is rendered
      Then  an <img> with alt text, loading=lazy and the thumb=list URL is in the row
    """
    client = _client(_image("list-a.jpg"))

    html = client.get("/admin/thumbphoto/").text

    assert '/admin/thumbphoto/1/file/photo?thumb=list" alt="Photo"' in html
    assert 'loading="lazy"' in html


def test_detail_view_links_the_200px_thumbnail_to_the_original() -> None:
    """
    Scenario: detail view shows 200x200 thumbnail with link to full image
      Given a record with a stored image
      When  the detail view is rendered
      Then  the thumb=detail image sits inside a link to the full-size file
    """
    client = _client(_image("detail-a.jpg"))

    html = client.get("/admin/thumbphoto/1").text

    assert '/admin/thumbphoto/1/file/photo?thumb=detail"' in html
    assert '/admin/thumbphoto/1/file/photo" target' in html
    assert "photo-thumbnail-link" in html


def test_update_form_previews_the_current_image() -> None:
    """
    Scenario: the image widget previews the stored image
      Given a record with a stored image
      When  the edit form is rendered
      Then  the widget shows the current file name and its thumbnail
    """
    client = _client(_image("form-a.jpg"))

    html = client.get("/admin/thumbphoto/1/edit").text

    assert '/admin/thumbphoto/1/file/photo?thumb=detail"' in html
    assert "photo-current-file" in html


def test_no_thumbnails_without_a_stored_image() -> None:
    """
    Scenario: nothing to thumbnail
      Given a record with no stored image
      When  the list is rendered
      Then  no thumbnail <img> is emitted
    """
    client = _client(None)

    assert "thumb=list" not in client.get("/admin/thumbphoto/").text
