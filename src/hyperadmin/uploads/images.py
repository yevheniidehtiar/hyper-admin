"""Image upload helpers: metadata, EXIF auto-rotation and cached thumbnails.

Everything here is a pure function over Pillow images or file-like objects.
The only side effects are the ones the caller asks for: rewriting an upload
in place (:func:`prepare_image_upload`) or writing a thumbnail file next to
its original (:func:`generate_thumbnail`).

Two guards apply to every image this module opens:

* **Non-image input** never raises. :func:`extract_metadata` and
  :func:`prepare_image_upload` return ``None`` and leave the stream rewound;
  :func:`generate_thumbnail` returns a placeholder.
* **Decompression bombs** are rejected before a single pixel is decoded.
  Pillow opens images lazily, so the header-declared size is compared with
  ``max_pixels`` (``Pillow``'s own ``MAX_IMAGE_PIXELS`` by default) and an
  :class:`ImageTooLargeError` is raised for anything larger.
"""

from __future__ import annotations

import io
import logging
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, TYPE_CHECKING, Any

from PIL import Image, ImageOps

from hyperadmin.core.storage_paths import resolve_storage_path
from hyperadmin.uploads.validation import FileValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.datastructures import UploadFile

logger = logging.getLogger(__name__)

#: Pixel budget (width x height) above which an image is treated as a bomb.
MAX_IMAGE_PIXELS: int = Image.MAX_IMAGE_PIXELS or 89_478_485
#: Directory, relative to the original, that holds its cached thumbnails.
THUMBNAIL_DIR = ".thumbs"
#: Static asset returned by :func:`generate_thumbnail` when no thumbnail can be made.
PLACEHOLDER_THUMBNAIL = "icons/file-text.svg"
#: Default bounding box for thumbnails.
DEFAULT_THUMBNAIL_SIZE: tuple[int, int] = (200, 200)

_ORIENTATION_TAG = 0x0112
_NORMAL_ORIENTATION = 1
# Pillow signals unreadable input with these (UnidentifiedImageError is an OSError).
_OPEN_ERRORS: tuple[type[Exception], ...] = (OSError, ValueError, SyntaxError, TypeError)


class ImageTooLargeError(FileValidationError):
    """Raised when an image declares more pixels than ``max_pixels`` allows."""


_THUMBNAIL_ERRORS: tuple[type[Exception], ...] = (ImageTooLargeError, *_OPEN_ERRORS)


@dataclass(frozen=True)
class ImageMetadata:
    """What an image says about itself, read from its header and EXIF block.

    Attributes:
        width: Pixel width as stored (before any EXIF rotation is applied).
        height: Pixel height as stored.
        format: Pillow format name, e.g. ``"JPEG"`` or ``"PNG"``.
        orientation: EXIF orientation tag (1-8); ``1`` means "already upright".
    """

    width: int
    height: int
    format: str
    orientation: int = _NORMAL_ORIENTATION

    @property
    def needs_rotation(self) -> bool:
        """``True`` when the EXIF orientation asks the viewer to transpose the pixels."""
        return self.orientation != _NORMAL_ORIENTATION


def _as_stream(source: Any) -> Any:
    """Unwrap an ``UploadFile`` to its underlying file; pass paths and streams through."""
    inner = getattr(source, "file", None)
    return inner if inner is not None and hasattr(inner, "read") else source


def _rewind(stream: Any) -> None:
    if hasattr(stream, "seek"):
        stream.seek(0)


@contextmanager
def _open_image(source: Any, *, max_pixels: int) -> Iterator[Image.Image]:
    """Open ``source`` lazily and refuse it before decoding if it is too large.

    A file Pillow opened itself (from a path) is closed on exit; a stream the
    caller passed in is left open for them.

    Raises:
        ImageTooLargeError: The header declares more than ``max_pixels`` pixels.
        OSError, ValueError, SyntaxError, TypeError: Pillow cannot read the input.
    """
    with warnings.catch_warnings():
        # The size is checked explicitly below; Pillow's own 1x warning is noise here.
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        try:
            image = Image.open(source)
        except Image.DecompressionBombError as exc:
            raise ImageTooLargeError(str(exc)) from exc
    with image:
        if image.width * image.height > max_pixels:
            raise ImageTooLargeError(
                f"Image of {image.width}x{image.height} pixels exceeds the limit of "
                f"{max_pixels} pixels"
            )
        yield image


def extract_metadata(
    source: str | Path | IO[bytes] | UploadFile,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> ImageMetadata | None:
    """Read dimensions, format and EXIF orientation without decoding pixels.

    Args:
        source: A path, a binary stream or a Starlette ``UploadFile``. Streams
            are rewound to position 0 afterwards.
        max_pixels: Decompression-bomb threshold (width x height).

    Returns:
        The metadata, or ``None`` when ``source`` is not an image Pillow can read.

    Raises:
        ImageTooLargeError: The image is larger than ``max_pixels``.
    """
    stream = _as_stream(source)
    try:
        with _open_image(stream, max_pixels=max_pixels) as image:
            orientation = int(image.getexif().get(_ORIENTATION_TAG, _NORMAL_ORIENTATION))
            return ImageMetadata(image.width, image.height, image.format or "", orientation)
    except ImageTooLargeError:
        raise
    except _OPEN_ERRORS:
        return None
    finally:
        _rewind(stream)


def auto_rotate(image: Image.Image) -> Image.Image:
    """Return ``image`` transposed so its pixels match the EXIF orientation.

    The returned image carries no orientation tag, so re-saving it will not
    rotate it twice. An image without an orientation tag is returned as a copy.
    """
    rotated = ImageOps.exif_transpose(image)
    return image if rotated is None else rotated


def prepare_image_upload(
    upload: UploadFile,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> ImageMetadata | None:
    """Normalise an uploaded image in place before the storage column saves it.

    This is the hook the form save path calls for ``ImageType`` fields. A
    non-image upload is left untouched. An image whose EXIF orientation says
    "rotate me" is re-encoded upright, in its original format and with the
    rest of its EXIF block, straight back into ``upload.file``.

    Args:
        upload: The multipart upload; its ``file`` is read, possibly rewritten,
            and always rewound.
        max_pixels: Decompression-bomb threshold (width x height).

    Returns:
        The metadata of the file as it will be stored, or ``None`` for a non-image.

    Raises:
        ImageTooLargeError: The image is larger than ``max_pixels``.
    """
    metadata = extract_metadata(upload, max_pixels=max_pixels)
    if metadata is None or not metadata.needs_rotation:
        return metadata
    stream = upload.file
    encoded = io.BytesIO()
    try:
        with _open_image(stream, max_pixels=max_pixels) as image:
            rotated = auto_rotate(image)
            save_kwargs: dict[str, Any] = {}
            if rotated.info.get("exif"):
                save_kwargs["exif"] = rotated.info["exif"]
            rotated.save(encoded, format=metadata.format, **save_kwargs)
    except _OPEN_ERRORS as exc:
        logger.warning("Upload %r could not be auto-rotated: %s", upload.filename, exc)
        _rewind(stream)
        return metadata
    stream.seek(0)
    stream.truncate()
    stream.write(encoded.getvalue())
    stream.seek(0)
    if hasattr(upload, "size"):
        upload.size = len(encoded.getvalue())
    return ImageMetadata(rotated.width, rotated.height, metadata.format)


def thumbnail_name(filename: str, max_size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE) -> str:
    """Return the storage-relative name of the thumbnail for ``filename``.

    ``photo.jpg`` at ``(100, 100)`` becomes ``.thumbs/photo_100x100.jpg``; a
    nested ``gallery/photo.jpg`` keeps its directory: ``gallery/.thumbs/...``.
    """
    original = PurePosixPath(filename)
    width, height = max_size
    return str(
        original.parent / THUMBNAIL_DIR / f"{original.stem}_{width}x{height}{original.suffix}"
    )


def generate_thumbnail(
    storage: Any,
    filename: str,
    max_size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE,
    *,
    max_pixels: int = MAX_IMAGE_PIXELS,
    placeholder: str = PLACEHOLDER_THUMBNAIL,
) -> str:
    """Return a thumbnail of ``filename`` that fits inside ``max_size``, making it once.

    The thumbnail is written under :data:`THUMBNAIL_DIR` next to the original,
    auto-rotated, with its aspect ratio preserved and LANCZOS resampling. A
    cached thumbnail is reused as long as it is not older than the original.

    Args:
        storage: A ``FileSystemStorage`` (or compatible object exposing
            ``get_path`` and a ``_path``/``path`` root).
        filename: The stored name of the original, as held by the file column.
        max_size: Bounding box ``(width, height)`` in pixels.
        max_pixels: Decompression-bomb threshold for the original.
        placeholder: Value returned when no thumbnail can be produced. The
            default is a static icon path, not a storage name.

    Returns:
        The storage-relative thumbnail name, or ``placeholder`` when the
        original is missing, outside the storage root, not an image, or too large.
    """
    source = resolve_storage_path(storage, filename)
    if source is None or not source.is_file():
        return placeholder
    name = thumbnail_name(filename, max_size)
    target = resolve_storage_path(storage, name)
    if target is None:
        return placeholder
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return name
    encoded = io.BytesIO()
    try:
        with _open_image(source, max_pixels=max_pixels) as image:
            thumb = auto_rotate(image)
            thumb.thumbnail(max_size, Image.Resampling.LANCZOS)
            thumb.save(encoded, format=image.format)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encoded.getvalue())
    except _THUMBNAIL_ERRORS as exc:
        logger.warning("Thumbnail for %r could not be generated: %s", filename, exc)
        return placeholder
    return name
