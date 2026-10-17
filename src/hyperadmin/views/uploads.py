"""Response and naming policy for stored upload files (BYOA SDD C.5).

Files are never served by a public static mount. ``DynamicModelView`` serves
them per record and field, after its permission, queryset and object checks,
and builds the response here:

- ``X-Content-Type-Options: nosniff`` and ``Content-Security-Policy: sandbox``
  on every file, so a stored HTML or SVG file can never run script in the
  admin's origin;
- ``Content-Disposition: inline`` only for an allow-list of raster image types
  (PNG, JPEG, GIF, WebP), and ``attachment`` for everything else, SVG included.

New uploads get a unique stored name, so one upload can never replace the file
another record points at.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from starlette.responses import FileResponse

#: Raster image types a browser may display inline. SVG is deliberately absent:
#: it is a document that can carry script.
INLINE_IMAGE_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

#: Headers sent with every stored file.
FILE_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox",
    "Cache-Control": "private",
}

_UNIQUE_PREFIX = re.compile(r"^[0-9a-f]{32}-(?=.)")


def unique_upload_name(storage: Any, client_name: str) -> str:
    """Return a fresh, root-level storage name derived from ``client_name``.

    Directory parts are dropped, the basename is sanitised with the storage's
    ``get_name`` when it has one, and a ``uuid4`` hex prefix makes the name
    unique, so an upload never replaces a stored file.

    The name is flat (``<uuid4 hex>-<secure name>``) rather than nested in a
    per-upload directory: ``fastapi-storages`` 0.1.0 flattens path separators
    on write, so a nested name would not round-trip on the lowest supported
    version.
    """
    basename = PurePosixPath(client_name.replace("\\", "/")).name
    get_name = getattr(storage, "get_name", None)
    safe = str(get_name(basename)) if callable(get_name) else basename
    safe = PurePosixPath(safe.replace("\\", "/")).name.lstrip(".")
    return f"{uuid.uuid4().hex}-{safe}" if safe else uuid.uuid4().hex


def download_name(stored_name: str) -> str:
    """Return the file name offered to the browser for ``stored_name``.

    The directory part and the unique prefix added by :func:`unique_upload_name`
    are dropped, so ``"3f…9a-report.pdf"`` downloads as ``"report.pdf"``.
    """
    basename = PurePosixPath(stored_name.replace("\\", "/")).name
    return _UNIQUE_PREFIX.sub("", basename)


def file_download_response(path: Path, stored_name: str) -> FileResponse:
    """Build the response for the stored file at ``path``.

    Args:
        path: The resolved file path, already contained in the storage root.
        stored_name: The name held by the file column.
    """
    name = download_name(stored_name)
    inline_type = INLINE_IMAGE_TYPES.get(Path(name).suffix.lower())
    return FileResponse(
        path,
        media_type=inline_type or "application/octet-stream",
        filename=name,
        content_disposition_type="inline" if inline_type else "attachment",
        headers=dict(FILE_SECURITY_HEADERS),
    )
