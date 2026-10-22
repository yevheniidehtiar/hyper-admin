"""File upload, download and deletion."""

import logging
import os
from typing import Any

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile as StarletteUpload
from starlette.responses import Response

from hyperadmin.core.storage_paths import resolve_storage_path, storage_root
from hyperadmin.views.dynamic.base import DynamicModelViewBase
from hyperadmin.views.dynamic.helpers import (
    _request_scoped,
)
from hyperadmin.views.uploads import file_download_response, unique_upload_name
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class FileViewMixin(DynamicModelViewBase):
    """File upload, download and deletion."""

    @_request_scoped
    async def upload_file_view(
        self,
        request: Request,
        field_name: str,
    ) -> Response:
        """Accept a file upload and store it via the configured storage.

        ``POST /{model}/upload/{field_name}``

        Requires ``add`` or ``change`` on the model, and ``field_name`` must be a
        file field (404 otherwise).

        The client-supplied name is never used as a path: only its sanitised
        basename is kept, a fresh name is generated so an existing file is never
        overwritten, and the target must resolve inside the storage root.

        Returns a JSON response with the stored name, relative to the storage root.
        """
        await self._check_any_permission(request, ("add", "change"))
        if field_name not in self._get_file_fields():
            raise HTTPException(status_code=404, detail=f"Unknown file field: {field_name!r}")
        if not self.storage:
            raise HTTPException(
                status_code=400,
                detail="File uploads not configured",
            )
        form_data = await request.form()
        upload = form_data.get("file")
        if not isinstance(upload, StarletteUpload) or not upload.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        name = self._new_upload_name(upload.filename)
        if storage_root(self.storage) is not None:
            target = resolve_storage_path(self.storage, name)
            if target is None or target.exists():
                raise HTTPException(status_code=400, detail="Invalid file name")
        self.storage.write(upload.file, name)
        from starlette.responses import JSONResponse  # noqa: PLC0415

        return JSONResponse({"filename": name})

    def _new_upload_name(self, client_name: str) -> str:
        """Return a fresh, unique storage name derived from ``client_name``."""
        return unique_upload_name(self.storage, client_name)

    def _file_urls(
        self, request: Request, item_id: Any, item_data: dict[str, Any], file_fields: set[str]
    ) -> dict[str, str]:
        """Map each shown, non-empty file field to its per-record download URL.

        Empty when no storage is configured, because the download route is then
        not registered.
        """
        if not self.storage:
            return {}
        route_name = f"{self._model_name_lower}-file"
        return {
            name: str(admin_url_for(request, route_name, item_id=item_id, field_name=name))
            for name in sorted(file_fields)
            if item_data.get(name)
        }

    @_request_scoped
    async def download_file_view(
        self,
        request: Request,
        item_id: Any,
        field_name: str,
    ) -> Response:
        """Stream the file stored in ``field_name`` of one record.

        ``GET /{model}/{item_id}/file/{field_name}``

        Requires ``view`` on the model. The record is loaded under the
        request's queryset filter and must pass the object ``view`` check.
        Returns 404 unless ``field_name`` is a non-sensitive file field whose
        stored name resolves to an existing file inside the storage root. The
        response policy (``nosniff``, ``CSP: sandbox``, attachment unless an
        allow-listed raster image) lives in :mod:`hyperadmin.views.uploads`.
        """
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "view")
        if field_name not in self._get_file_fields() - self._sensitive_fields:
            raise HTTPException(status_code=404, detail="File not found")
        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "view")
        value: Any = getattr(item, field_name, None)
        path = self._stored_file_path(value)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        stored_name = value.name if hasattr(value, "name") else str(value)
        return file_download_response(path, stored_name)

    @_request_scoped
    async def delete_file_view(
        self,
        request: Request,
        item_id: Any,
        field_name: str,
    ) -> Response:
        """Delete a file from storage and clear the field on the record.

        ``DELETE /{model}/{item_id}/file/{field_name}``

        ``field_name`` must be a file field (404 otherwise), and the file is
        removed only when its path resolves inside the storage root.
        """
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "change")
        if field_name not in self._get_file_fields():
            raise HTTPException(status_code=404, detail=f"Unknown file field: {field_name!r}")
        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "change")
        path = self._stored_file_path(getattr(item, field_name, None))
        if path is not None:
            self._remove_files([str(path)])
        await self.adapter.update(pk=pk, data={field_name: None})
        if "hx-request" in request.headers:
            return Response(
                status_code=200,
                headers={"HX-Trigger": "fileDeleted"},
            )
        return Response(status_code=204)

    def _collect_file_paths(self, item: Any) -> list[str]:
        """Return disk paths of all files attached to *item*.

        The paths are collected **before** the DB row is deleted so that
        ``ImageType.process_result_value`` (which opens the file) is not
        called after the file has already been removed.
        """
        if not self.storage:
            return []
        paths: list[str] = []
        for name in sorted(self._get_file_fields()):
            path = self._stored_file_path(getattr(item, name, None))
            if path is not None:
                paths.append(str(path))
        return paths

    def _stored_file_path(self, value: Any) -> Any:
        """Resolve a file column value to a path inside the storage root, or ``None``."""
        if not value or not self.storage:
            return None
        name = value.name if hasattr(value, "name") else str(value)
        return resolve_storage_path(self.storage, name)

    @staticmethod
    def _remove_files(paths: list[str]) -> None:
        """Remove regular files from disk, ignoring missing ones.

        Paths must come from :func:`resolve_storage_path` (storage-root contained).
        """
        for path in paths:
            if os.path.isfile(path):
                os.remove(path)
