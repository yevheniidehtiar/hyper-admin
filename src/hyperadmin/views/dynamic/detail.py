"""The detail view and its panels."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import Response, StreamingResponse

from hyperadmin.core.display import get_display_name
from hyperadmin.core.panels import PanelDef, panel_permission_codename
from hyperadmin.core.schema import dump_instance
from hyperadmin.views.dynamic.files import FileViewMixin
from hyperadmin.views.dynamic.helpers import (
    _as_attachment,
    _discard_stream,
    _disposition_filename,
    _human_size,
    _request_scoped,
)
from hyperadmin.views.uploads import download_name
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class DetailViewMixin(FileViewMixin):
    """The detail view and its panels."""

    @_request_scoped
    async def detail_view(self, request: Request, item_id: Any):
        """Renders the detail view for a single item, keyed by the model's primary key."""
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "view")
        item = await self._get_or_404(pk)

        await self._check_object_permission(request, item, "view")

        file_fields = self._get_file_fields()
        item_data = self._without_sensitive(dump_instance(item))
        for fname in file_fields - self._sensitive_fields:
            val = getattr(item, fname, None)
            if val is not None:
                item_data[fname] = val.name if hasattr(val, "name") else str(val)

        file_urls = self._file_urls(request, item_id, item_data, file_fields)
        context = {
            "request": request,
            "item_name": get_display_name(item),
            "item": item_data,
            "field_labels": self.field_labels,
            "actions": self.actions,
            "model_name_lower": self._model_name_lower,
            "file_fields": file_fields,
            "file_urls": file_urls,
            "thumb_urls": self._thumbnail_urls(request, item_id, item_data, "detail"),
            "file_labels": {name: download_name(item_data[name]) for name in file_urls},
            "pk_attr": self.pk.attr,
            "panels": await self._visible_panels(request, item, item_id),
        }
        template_name = self._get_template_name("detail")
        return self.templates.TemplateResponse(request, template_name, context)

    def _panel_codename(self, panel_def: PanelDef) -> str:
        """Return the permission codename guarding ``panel_def``."""
        return panel_def.permission or panel_permission_codename(self.model, panel_def.slug)

    def _panel_or_404(self, slug: str) -> PanelDef:
        """Return the registered panel for ``slug`` or raise 404 ``"Unknown panel"``."""
        panel_def = self._panel_map.get(slug)
        if panel_def is None:
            raise HTTPException(status_code=404, detail="Unknown panel")
        return panel_def

    async def _visible_panels(
        self, request: Request, item: Any, item_id: Any
    ) -> list[dict[str, Any]]:
        """Return the panels the detail page shows for ``item``, in declared order.

        A panel is listed when its ``enabled`` predicate accepts ``item`` and the
        user holds its permission codename, so the tab strip never shows a tab
        that could only answer 403 or 404. Each entry carries ``slug``,
        ``label``, ``icon`` and the ``url`` of its ``render_panel_view``.
        """
        visible: list[dict[str, Any]] = []
        for panel_def in self.panels:
            if panel_def.enabled is not None and not panel_def.enabled(item):
                continue
            if not await self._has_permission(request, self._panel_codename(panel_def)):
                continue
            url = admin_url_for(
                request, f"{self._model_name_lower}-panel", item_id=item_id, slug=panel_def.slug
            )
            visible.append(
                {
                    "slug": panel_def.slug,
                    "label": panel_def.label,
                    "icon": panel_def.icon,
                    "url": str(url),
                }
            )
        return visible

    async def _load_panel_target(self, request: Request, item_id: Any, panel_def: PanelDef) -> Any:
        """Run every check both panel routes share and return the loaded record.

        In order: ``view_{model}`` (a panel is part of the detail page), the
        panel's own codename, the record under the request's queryset scope
        (404 when hidden or missing), the object ``view`` check, and finally the
        ``enabled`` predicate — a hidden tab's URL is a 404, never a leak.
        """
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "view")
        if not await self._has_permission(request, self._panel_codename(panel_def)):
            raise HTTPException(status_code=403, detail="Permission denied")
        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "view")
        if panel_def.enabled is not None and not panel_def.enabled(item):
            raise HTTPException(status_code=404, detail="Unknown panel")
        return item

    async def _run_panel_handler(
        self, request: Request, panel_def: PanelDef, item: Any
    ) -> Response:
        """Call the panel handler with the loaded record and insist on a ``Response``."""
        # ``Any``: the declared return type is a promise the handler may break.
        result: Any = await panel_def.handler(request, item)
        if not isinstance(result, Response):
            logger.error(
                "panel %r on %s returned %s, not a Response",
                panel_def.slug,
                self.model.__name__,
                type(result).__name__,
            )
            raise TypeError(
                f"panel {panel_def.slug!r} handler must return a starlette Response, "
                f"got {type(result).__name__}"
            )
        return result

    @_request_scoped
    async def render_panel_view(self, request: Request, item_id: Any, slug: str) -> Response:
        """Render one panel's body for the detail page's lazy-loading tab.

        ``GET /{model}/{item_id}/panels/{slug}``

        An ``HTMLResponse`` (any non-streaming ``Response``) is returned as the
        fragment to swap inline. A ``StreamingResponse`` is *not* sent: its type
        alone is inspected, and the document viewer fragment pointing at
        :meth:`stream_panel_view` is rendered instead, so binary bodies never go
        through an HTMX swap. A 403 from any check — or raised by the handler —
        becomes the forbidden panel state, retargeted to the panel element that
        asked (``HX-Retarget: this``), so sibling tabs keep working.
        """
        panel_def = self._panel_or_404(slug)
        try:
            item = await self._load_panel_target(request, item_id, panel_def)
            result = await self._run_panel_handler(request, panel_def, item)
        except HTTPException as exc:
            if exc.status_code != HTTPStatus.FORBIDDEN:
                raise
            return self._render_panel_forbidden(request, panel_def)
        if isinstance(result, StreamingResponse):
            await _discard_stream(result)
            return self._render_panel_document(request, item_id, panel_def, result)
        return result

    @_request_scoped
    async def stream_panel_view(self, request: Request, item_id: Any, slug: str) -> Response:
        """Serve a streaming panel's bytes for the viewer frame or a download.

        ``GET /{model}/{item_id}/panels/{slug}/stream[?download=1]``

        Re-runs every check :meth:`render_panel_view` runs, then returns the
        handler's response as-is with ``Content-Disposition`` forced to
        ``inline`` when the handler set none, or to ``attachment`` when
        ``?download`` is present (the viewer's Download button). Errors here
        propagate to ``HyperAdminRoute``, which renders them inside the frame.
        """
        panel_def = self._panel_or_404(slug)
        item = await self._load_panel_target(request, item_id, panel_def)
        result = await self._run_panel_handler(request, panel_def, item)
        disposition = result.headers.get("content-disposition", "")
        if "download" in request.query_params:
            result.headers["content-disposition"] = _as_attachment(disposition)
        elif not disposition:
            result.headers["content-disposition"] = "inline"
        return result

    def _render_panel_forbidden(self, request: Request, panel_def: PanelDef) -> Response:
        """Render the 403 panel state into the requesting panel element."""
        context = {
            "request": request,
            "state": "forbidden",
            "panel": panel_def,
            "permission": self._panel_codename(panel_def),
        }
        response = self.templates.TemplateResponse(
            request, "components/panel_states.html", context, status_code=403
        )
        # ``_base.html`` lets HTMX swap a 403 only when it is retargeted; ``this``
        # is the element that issued the hx-get, i.e. the panel body itself.
        response.headers["HX-Retarget"] = "this"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    def _render_panel_document(
        self, request: Request, item_id: Any, panel_def: PanelDef, result: StreamingResponse
    ) -> Response:
        """Render the document viewer fragment for a streaming panel."""
        stream_url = str(
            admin_url_for(
                request,
                f"{self._model_name_lower}-panel-stream",
                item_id=item_id,
                slug=panel_def.slug,
            )
        )
        context = {
            "request": request,
            "panel": panel_def,
            "stream_url": stream_url,
            "download_url": f"{stream_url}?download=1",
            "file_name": _disposition_filename(result.headers.get("content-disposition"))
            or panel_def.label,
            "file_size": _human_size(result.headers.get("content-length")),
            "media_type": result.headers.get("content-type", ""),
        }
        return self.templates.TemplateResponse(request, "components/panel_document.html", context)
