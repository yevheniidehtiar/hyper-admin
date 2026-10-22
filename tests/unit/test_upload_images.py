"""Unit tests for ``hyperadmin.uploads.images`` — metadata, EXIF auto-rotate, thumbnails.

Stories: #404 (thumbnail generation helper) and #408 (EXIF metadata + auto-rotate),
epic #410. Fixtures are tiny images generated with Pillow at test time.
"""

from __future__ import annotations

import io
import logging
import os
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from fastapi_storages import FileSystemStorage
from PIL import Image
from starlette.datastructures import UploadFile

from hyperadmin.uploads import (
    PLACEHOLDER_THUMBNAIL,
    ImageMetadata,
    ImageTooLargeError,
    auto_rotate,
    extract_metadata,
    generate_thumbnail,
    prepare_image_upload,
    thumbnail_name,
)
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.forms import FileInputWidget, TextInput

if TYPE_CHECKING:
    from collections.abc import Callable

ORIENTATION = 0x0112
ROTATED_90_CW = 6

# ---------------------------------------------------------------------------
# Fixture helpers: tiny generated images
# ---------------------------------------------------------------------------


def _image_bytes(
    width: int,
    height: int,
    fmt: str = "JPEG",
    *,
    orientation: int | None = None,
    mode: str = "RGB",
) -> bytes:
    """Encode a solid-colour ``width``x``height`` image, optionally with an EXIF orientation."""
    image = Image.new(mode, (width, height), "red")
    buffer = io.BytesIO()
    if orientation is None:
        image.save(buffer, format=fmt)
    else:
        exif = Image.Exif()
        exif[ORIENTATION] = orientation
        exif[0x010F] = "HyperAdmin test camera"  # Make
        image.save(buffer, format=fmt, exif=exif.tobytes())
    return buffer.getvalue()


def _png_header_only(width: int, height: int) -> bytes:
    """A PNG signature + IHDR chunk declaring ``width``x``height`` with no pixel data.

    Pillow reads the declared size from the header before decoding, which is
    exactly where a decompression bomb must be caught.
    """

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        return struct.pack(">I", len(payload)) + kind + payload + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def _upload(data: bytes, filename: str = "photo.jpg") -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=filename, size=len(data))


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------


def test_extract_metadata_reads_dimensions_and_format_from_jpeg(tmp_path: Path) -> None:
    """Scenario: extract dimensions from uploaded image.

    Given a JPEG image 3000x2000
    When extract_metadata(file) is called
    Then the result includes width=3000, height=2000, format="JPEG"
    """
    path = tmp_path / "big.jpg"
    path.write_bytes(_image_bytes(3000, 2000))

    meta = extract_metadata(path)

    assert meta == ImageMetadata(width=3000, height=2000, format="JPEG", orientation=1)
    assert meta.needs_rotation is False


def test_extract_metadata_accepts_upload_file_and_rewinds_it() -> None:
    """Scenario: metadata from an UploadFile leaves the stream at position 0."""
    upload = _upload(_image_bytes(8, 4, "PNG"), "shot.png")
    upload.file.read(3)  # the caller may already have peeked at the stream

    meta = extract_metadata(upload)

    assert meta == ImageMetadata(8, 4, "PNG")
    assert upload.file.tell() == 0


def test_extract_metadata_reports_exif_orientation() -> None:
    """Scenario: a camera-rotated JPEG reports its orientation tag."""
    meta = extract_metadata(io.BytesIO(_image_bytes(4, 2, orientation=ROTATED_90_CW)))

    assert meta is not None
    assert meta.orientation == ROTATED_90_CW
    assert meta.needs_rotation is True


def test_extract_metadata_returns_none_for_non_image() -> None:
    """Scenario: non-image file returns None metadata.

    Given a PDF file
    When extract_metadata(file) is called
    Then the result is None (no exception raised) and the stream is rewound
    """
    stream = io.BytesIO(PDF_BYTES)

    assert extract_metadata(stream) is None
    assert stream.tell() == 0


def test_extract_metadata_returns_none_for_missing_path(tmp_path: Path) -> None:
    """Scenario: a path that does not exist is not an image either."""
    assert extract_metadata(tmp_path / "nope.jpg") is None


def test_extract_metadata_rejects_decompression_bomb_from_header() -> None:
    """Scenario: an image declaring 10 gigapixels is refused before decoding."""
    stream = io.BytesIO(_png_header_only(100_000, 100_000))

    with pytest.raises(ImageTooLargeError):
        extract_metadata(stream)
    assert stream.tell() == 0


def test_extract_metadata_honours_custom_pixel_budget() -> None:
    """Scenario: a 4x4 image is too large for a 10-pixel budget."""
    with pytest.raises(ImageTooLargeError, match="4x4 pixels exceeds the limit of 10"):
        extract_metadata(io.BytesIO(_image_bytes(4, 4, "PNG")), max_pixels=10)


# ---------------------------------------------------------------------------
# auto_rotate
# ---------------------------------------------------------------------------


def test_auto_rotate_transposes_to_exif_orientation() -> None:
    """Scenario: auto-rotate based on EXIF orientation tag.

    Given a JPEG with EXIF orientation tag = 6 (rotated 90° CW by camera)
    When the image is processed via auto_rotate(image)
    Then the image is rotated to correct orientation and the tag is dropped
    """
    with Image.open(io.BytesIO(_image_bytes(4, 2, orientation=ROTATED_90_CW))) as image:
        rotated = auto_rotate(image)

    assert rotated.size == (2, 4)
    assert ORIENTATION not in rotated.getexif()


def test_auto_rotate_keeps_upright_image_as_is() -> None:
    """Scenario: an image without an orientation tag keeps its size and pixels."""
    with Image.open(io.BytesIO(_image_bytes(4, 2, "PNG"))) as image:
        rotated = auto_rotate(image)

    assert rotated.size == (4, 2)


def test_auto_rotate_falls_back_to_input_when_pillow_returns_none(monkeypatch) -> None:
    """Scenario: a transposer that yields nothing leaves the original image in play."""
    monkeypatch.setattr("hyperadmin.uploads.images.ImageOps.exif_transpose", lambda img: None)
    image = Image.new("RGB", (3, 1))

    assert auto_rotate(image) is image


# ---------------------------------------------------------------------------
# prepare_image_upload (the save-path hook)
# ---------------------------------------------------------------------------


def test_prepare_image_upload_rewrites_rotated_image_in_place() -> None:
    """Scenario: a camera-rotated upload is stored upright, keeping its other EXIF."""
    upload = _upload(_image_bytes(4, 2, orientation=ROTATED_90_CW))

    meta = prepare_image_upload(upload)

    assert meta == ImageMetadata(2, 4, "JPEG")
    assert upload.file.tell() == 0
    stored = upload.file.read()
    assert upload.size == len(stored)
    with Image.open(io.BytesIO(stored)) as image:
        assert image.format == "JPEG"
        assert image.size == (2, 4)
        exif = image.getexif()
        assert ORIENTATION not in exif
        assert exif[0x010F] == "HyperAdmin test camera"


def test_prepare_image_upload_leaves_upright_image_untouched() -> None:
    """Scenario: an upright image is passed through byte for byte."""
    data = _image_bytes(4, 2, "PNG")
    upload = _upload(data, "shot.png")

    meta = prepare_image_upload(upload)

    assert meta == ImageMetadata(4, 2, "PNG")
    assert upload.file.read() == data


def test_prepare_image_upload_ignores_non_image() -> None:
    """Scenario: a PDF on an image field is neither rotated nor refused here."""
    upload = _upload(PDF_BYTES, "doc.pdf")

    assert prepare_image_upload(upload) is None
    assert upload.file.read() == PDF_BYTES


def test_prepare_image_upload_refuses_decompression_bomb() -> None:
    """Scenario: a bomb upload raises before any pixel is decoded."""
    upload = _upload(_png_header_only(100_000, 100_000), "bomb.png")

    with pytest.raises(ImageTooLargeError):
        prepare_image_upload(upload)


def test_prepare_image_upload_keeps_original_when_reencode_fails(monkeypatch, caplog) -> None:
    """Scenario: if Pillow cannot re-encode the rotated image, the original bytes survive."""
    data = _image_bytes(4, 2, orientation=ROTATED_90_CW)
    upload = _upload(data)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("encoder failed")

    monkeypatch.setattr(Image.Image, "save", _boom)
    with caplog.at_level(logging.WARNING, logger="hyperadmin.uploads.images"):
        meta = prepare_image_upload(upload)

    assert meta == ImageMetadata(4, 2, "JPEG", orientation=ROTATED_90_CW)
    assert upload.file.read() == data
    assert "could not be auto-rotated" in caplog.text


# ---------------------------------------------------------------------------
# thumbnail_name / generate_thumbnail
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(tmp_path: Path) -> FileSystemStorage:
    return FileSystemStorage(str(tmp_path / "media"))


@pytest.fixture
def put_file(storage: FileSystemStorage) -> Callable[[str, bytes], Path]:
    def _put(name: str, data: bytes) -> Path:
        path = Path(storage.get_path(name))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    return _put


def test_thumbnail_name_includes_size_suffix_and_keeps_directory() -> None:
    """Scenario: thumbnail path includes size suffix."""
    assert thumbnail_name("photo.jpg", (100, 100)) == ".thumbs/photo_100x100.jpg"
    assert thumbnail_name("gallery/2026/photo.png", (40, 40)) == (
        "gallery/2026/.thumbs/photo_40x40.png"
    )


def test_generate_thumbnail_preserves_aspect_ratio(storage, put_file) -> None:
    """Scenario: generate thumbnail preserving aspect ratio.

    Given an image 1920x1080
    When generate_thumbnail(storage, filename, max_size=(200, 200)) is called
    Then the thumbnail is 200x112 (landscape, aspect ratio preserved)
    """
    put_file("photo.jpg", _image_bytes(1920, 1080))

    name = generate_thumbnail(storage, "photo.jpg", max_size=(200, 200))

    assert name == ".thumbs/photo_200x200.jpg"
    with Image.open(storage.get_path(name)) as thumb:
        # 1080 * 200 / 1920 = 112.5; Pillow rounds the short side half-up (113) since 12.x
        assert thumb.size[0] == 200
        assert thumb.size[1] in (112, 113)
        assert thumb.format == "JPEG"


def test_generate_thumbnail_is_stored_at_size_suffixed_path(storage, put_file) -> None:
    """Scenario: thumbnail path includes size suffix.

    Given photo.jpg in storage
    When generate_thumbnail(storage, "photo.jpg", max_size=(100, 100)) is called
    Then the thumbnail is stored at .thumbs/photo_100x100.jpg
    """
    put_file("photo.jpg", _image_bytes(300, 300))

    name = generate_thumbnail(storage, "photo.jpg", max_size=(100, 100))

    assert name == ".thumbs/photo_100x100.jpg"
    assert Path(storage.get_path(".thumbs/photo_100x100.jpg")).is_file()


def test_generate_thumbnail_applies_exif_rotation(storage, put_file) -> None:
    """Scenario: a camera-rotated original yields an upright thumbnail."""
    put_file("portrait.jpg", _image_bytes(400, 200, orientation=ROTATED_90_CW))

    name = generate_thumbnail(storage, "portrait.jpg", max_size=(100, 100))

    with Image.open(storage.get_path(name)) as thumb:
        assert thumb.size == (50, 100)


def test_generate_thumbnail_is_cached_on_second_call(storage, put_file, monkeypatch) -> None:
    """Scenario: thumbnail is cached on second call.

    Given a thumbnail was already generated for photo.jpg at (200, 200)
    When generate_thumbnail() is called again with the same params
    Then the cached thumbnail path is returned without re-processing
    """
    put_file("photo.jpg", _image_bytes(400, 300))
    first = generate_thumbnail(storage, "photo.jpg")

    def _must_not_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("cached thumbnail was re-processed")

    monkeypatch.setattr("hyperadmin.uploads.images.Image.open", _must_not_open)
    second = generate_thumbnail(storage, "photo.jpg")

    assert first == second == ".thumbs/photo_200x200.jpg"


def test_generate_thumbnail_regenerates_stale_cache(storage, put_file) -> None:
    """Scenario: a thumbnail older than its original is rebuilt."""
    source = put_file("photo.jpg", _image_bytes(400, 300))
    name = generate_thumbnail(storage, "photo.jpg", max_size=(100, 100))
    thumb_path = Path(storage.get_path(name))
    os.utime(thumb_path, (1, 1))  # 1970: older than any source
    source.write_bytes(_image_bytes(300, 400))

    assert generate_thumbnail(storage, "photo.jpg", max_size=(100, 100)) == name
    with Image.open(thumb_path) as thumb:
        assert thumb.size == (75, 100)


def test_generate_thumbnail_returns_placeholder_for_corrupt_image(
    storage, put_file, caplog
) -> None:
    """Scenario: corrupt image returns placeholder.

    Given an image file that cannot be opened by Pillow
    When generate_thumbnail() is called
    Then a placeholder image path is returned and no exception is raised
    """
    put_file("broken.jpg", b"\xff\xd8\xff definitely not a jpeg")

    with caplog.at_level(logging.WARNING, logger="hyperadmin.uploads.images"):
        result = generate_thumbnail(storage, "broken.jpg")

    assert result == PLACEHOLDER_THUMBNAIL
    assert "could not be generated" in caplog.text
    assert not Path(storage.get_path(".thumbs")).exists()


def test_generate_thumbnail_returns_custom_placeholder_for_bomb(storage, put_file) -> None:
    """Scenario: a decompression bomb in storage yields the caller's placeholder."""
    put_file("bomb.png", _png_header_only(100_000, 100_000))

    assert generate_thumbnail(storage, "bomb.png", placeholder="/static/x.svg") == "/static/x.svg"


def test_generate_thumbnail_returns_placeholder_for_missing_file(storage) -> None:
    """Scenario: a stored name with no file behind it yields the placeholder."""
    assert generate_thumbnail(storage, "ghost.jpg") == PLACEHOLDER_THUMBNAIL


def test_generate_thumbnail_refuses_paths_outside_storage_root(storage, tmp_path: Path) -> None:
    """Scenario: a traversal name never reads or writes outside the storage root."""
    outside = tmp_path / "secret.jpg"
    outside.write_bytes(_image_bytes(10, 10))

    assert generate_thumbnail(storage, "../secret.jpg") == PLACEHOLDER_THUMBNAIL
    assert not (tmp_path / ".thumbs").exists()


def test_generate_thumbnail_without_storage_root_returns_placeholder() -> None:
    """Scenario: a storage object that exposes no root cannot be thumbnailed safely."""
    assert generate_thumbnail(object(), "photo.jpg") == PLACEHOLDER_THUMBNAIL


def test_generate_thumbnail_placeholder_when_target_escapes_root(
    storage, put_file, monkeypatch
) -> None:
    """Scenario: a thumbnail name that resolves outside the root is refused too."""
    put_file("photo.jpg", _image_bytes(10, 10))
    monkeypatch.setattr(
        "hyperadmin.uploads.images.thumbnail_name", lambda *_a, **_k: "../escape.jpg"
    )

    assert generate_thumbnail(storage, "photo.jpg") == PLACEHOLDER_THUMBNAIL


# ---------------------------------------------------------------------------
# DynamicModelView._pop_file_uploads calls the hook for image fields
# ---------------------------------------------------------------------------


def _fake_view() -> SimpleNamespace:
    """The two collaborators ``_pop_file_uploads`` reaches through ``self``."""
    return SimpleNamespace(
        _new_upload_name=lambda name: f"stored-{name}",
        _prepare_image_upload=DynamicModelView._prepare_image_upload,
    )


def _form(*fields: tuple[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        fields=[SimpleNamespace(name=name, widget=widget) for name, widget in fields]
    )


def test_pop_file_uploads_auto_rotates_image_fields() -> None:
    """Scenario: the form save path rotates an ImageType upload before storage sees it."""
    upload = _upload(_image_bytes(4, 2, orientation=ROTATED_90_CW))
    data = {"photo": upload, "title": "x"}

    uploads = DynamicModelView._pop_file_uploads(
        _fake_view(), data, _form(("photo", FileInputWidget(is_image=True)), ("title", TextInput()))
    )

    assert uploads == {"photo": upload}
    assert data == {"title": "x"}
    assert upload.filename == "stored-photo.jpg"
    with Image.open(upload.file) as image:
        assert image.size == (2, 4)


def test_pop_file_uploads_leaves_plain_file_fields_alone() -> None:
    """Scenario: a FileType upload that happens to be a rotated JPEG is stored verbatim."""
    data_bytes = _image_bytes(4, 2, orientation=ROTATED_90_CW)
    upload = _upload(data_bytes, "attachment.jpg")

    uploads = DynamicModelView._pop_file_uploads(
        _fake_view(), {"doc": upload}, _form(("doc", FileInputWidget(is_image=False)))
    )

    assert uploads == {"doc": upload}
    assert upload.file.read() == data_bytes


def test_pop_file_uploads_refuses_decompression_bomb_with_422() -> None:
    """Scenario: a bomb on an image field is refused with a field-keyed 422."""
    upload = _upload(_png_header_only(100_000, 100_000), "bomb.png")

    with pytest.raises(HTTPException) as excinfo:
        DynamicModelView._pop_file_uploads(
            _fake_view(), {"photo": upload}, _form(("photo", FileInputWidget(is_image=True)))
        )

    assert excinfo.value.status_code == 422
    assert "photo" in excinfo.value.detail
