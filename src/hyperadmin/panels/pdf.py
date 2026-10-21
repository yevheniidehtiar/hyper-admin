"""``pdf_stream_panel``: a bundled panel that streams a PDF file inline.

The one demo panel the detail-panels spec ships, so the streaming path of
``render_panel_view`` / ``stream_panel_view`` can be exercised without
consumer code. The handler returns a :class:`StreamingResponse`, which the
render view wraps in the document viewer fragment; the bytes themselves are
served on demand from the ``/stream`` sub-route.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import anyio
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from hyperadmin.core.panels import PanelDef

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.requests import Request

__all__ = ["PDF_MEDIA_TYPE", "PDFStreamPanel", "pdf_stream_panel", "pdf_stream_response"]

PDF_MEDIA_TYPE = "application/pdf"

#: Bytes read per chunk while streaming a file.
CHUNK_SIZE = 64 * 1024

#: Headers sent with every streamed document: never sniffed, never cached once
#: the permission that allowed the request is gone.
STREAM_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
}


def pdf_stream_panel(
    *,
    slug: str,
    label: str,
    path_resolver: Callable[[Any], Path | str],
    enabled: Callable[[Any], bool] | None = None,
    icon: str | None = None,
    permission: str | None = None,
) -> PanelDef:
    """Return a :class:`PanelDef` whose handler streams a PDF with ``inline`` disposition.

    Args:
        slug: Panel slug (URL segment and permission codename suffix).
        label: Tab label.
        path_resolver: ``(instance) -> Path`` giving the on-disk PDF for the
            loaded record. It runs on every panel request, so it must be cheap.
        enabled: Optional ``(instance) -> bool`` predicate; ``False`` hides the tab.
        icon: Optional tab icon name.
        permission: Explicit permission codename; ``None`` derives
            ``view_{model}_panel_{slug}`` at registration.

    The handler raises ``HTTPException(404, "Document not found")`` when the
    resolved path is not a file, so a missing document never becomes a 500.
    """

    async def handler(request: Request, obj: Any) -> StreamingResponse:  # noqa: ARG001 - panel contract
        path = Path(path_resolver(obj))
        async_path = anyio.Path(path)
        if not await async_path.is_file():
            raise HTTPException(status_code=404, detail="Document not found")
        return pdf_stream_response(path, size=(await async_path.stat()).st_size)

    return PanelDef(
        slug=slug,
        label=label,
        handler=handler,
        icon=icon,
        permission=permission,
        enabled=enabled,
    )


#: Class-style alias of :func:`pdf_stream_panel` (the spec names the factory both ways).
PDFStreamPanel = pdf_stream_panel


def pdf_stream_response(
    path: Path, *, filename: str | None = None, size: int | None = None
) -> StreamingResponse:
    """Build the inline ``application/pdf`` streaming response for ``path``.

    The file is opened lazily, inside the body iterator, so building the
    response (which ``render_panel_view`` does only to inspect its type) never
    touches the file. ``Content-Length`` is ``size`` when given (the panel
    handler stats the file without blocking), else a ``stat`` here, so the
    viewer can show the size and the browser can show progress.
    """
    name = filename or path.name
    headers = {
        "Content-Disposition": f"inline; {_filename_param(name)}",
        "Content-Length": str(path.stat().st_size if size is None else size),
        **STREAM_HEADERS,
    }
    return StreamingResponse(_read_chunks(path), media_type=PDF_MEDIA_TYPE, headers=headers)


def _filename_param(name: str) -> str:
    """Return the ``filename`` parameter for a ``Content-Disposition`` header.

    ASCII names without quotes use the plain form every browser understands;
    anything else uses RFC 5987 ``filename*`` encoding, as Starlette's
    ``FileResponse`` does.
    """
    if name.isascii() and '"' not in name:
        return f'filename="{name}"'
    return f"filename*=utf-8''{quote(name)}"


async def _read_chunks(path: Path) -> AsyncIterator[bytes]:
    async with await anyio.open_file(path, "rb") as handle:
        while chunk := await handle.read(CHUNK_SIZE):
            yield chunk
