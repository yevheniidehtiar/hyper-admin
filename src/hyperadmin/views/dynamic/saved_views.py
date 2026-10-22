"""Per-user saved list views."""

import functools
import logging
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse, RedirectResponse, Response

from hyperadmin.filters.saved_views import (
    SavedView,
    SavedViewNameTakenError,
    SavedViewService,
    normalize_querystring,
)
from hyperadmin.views.dynamic.base import DynamicModelViewBase
from hyperadmin.views.error_pages import wants_html
from hyperadmin.views.urls import SCOPE_KEY, admin_url_for

logger = logging.getLogger(__name__)


class SavedViewsMixin(DynamicModelViewBase):
    """Per-user saved list views."""

    @functools.cached_property
    def _saved_views(self) -> SavedViewService:
        return SavedViewService(
            getattr(self.adapter, "engine", None),
            session_factory=getattr(self.adapter, "session_factory", None),
        )

    def _saved_views_available(self, request: Request) -> bool:
        """Saved views need the option on and a mounted admin (the panel builds route URLs)."""
        scope = getattr(request, "scope", None) or {}
        return bool(self.options.saved_views_enabled) and SCOPE_KEY in scope

    def _saved_views_user(self, request: Request) -> Any:
        """The owner key of the request's user; 403 when nobody is signed in."""
        user_key = getattr(request.state, "user_key", None)
        if user_key is None:
            raise HTTPException(status_code=403, detail="Saved views need a signed-in user")
        return user_key

    def _saved_view_href(self, request: Request, view: SavedView) -> str:
        path = self._list_path(request)
        return f"{path}?{view.querystring}" if view.querystring else path

    def _saved_view_payload(self, request: Request, view: SavedView) -> dict[str, Any]:
        return {
            "id": view.id,
            "name": view.name,
            "querystring": view.querystring,
            "href": self._saved_view_href(request, view),
            "is_default": view.is_default,
            "created_at": view.created_at.isoformat(),
        }

    async def _resolve_saved_view(self, request: Request, raw_id: str) -> str:
        """The list URL a ``?view=<id>`` link stands for; 404 unless the view is the user's."""
        user_key = getattr(request.state, "user_key", None)
        view = (
            await self._saved_views.get(user_key, self._model_name_lower, int(raw_id))
            if raw_id.isdigit() and user_key is not None
            else None
        )
        if view is None:
            raise HTTPException(status_code=404, detail="Saved view not found")
        return self._saved_view_href(request, view)

    async def _saved_views_context(self, request: Request, *, loaded: bool) -> dict[str, Any]:
        """Template context for the saved-views panel: the user's views, the active one, URLs.

        ``loaded`` is false after a failed list query, when nothing else should
        touch the database. A missing ``hyperadmin_saved_view`` table never
        breaks the list page: the panel is left out and a warning names the fix.
        """
        context: dict[str, Any] = {
            "saved_views_enabled": False,
            "saved_views": [],
            "active_saved_view_id": None,
            "current_query": "",
            "saved_views_url": None,
        }
        user_key = getattr(request.state, "user_key", None)
        if not loaded or user_key is None or not self._saved_views_available(request):
            return context
        current = context["current_query"] = normalize_querystring(request.query_params)
        try:
            views = await self._saved_views.list_for(user_key, self._model_name_lower)
        except SQLAlchemyError:
            logger.warning(
                "Saved views for %s are unavailable; create the hyperadmin_saved_view table "
                "(existing-app guide, section 5) or set AdminOptions.saved_views_enabled=False",
                self.model.__name__,
                exc_info=True,
            )
            return context
        slug = self._model_name_lower
        context["saved_views_enabled"] = True
        context["saved_views_url"] = str(admin_url_for(request, f"{slug}-saved-views"))
        for view in views:
            payload = self._saved_view_payload(request, view)
            payload["active"] = view.querystring == current
            payload["delete_url"] = str(
                admin_url_for(request, f"{slug}-saved-view-delete", view_id=view.id)
            )
            if payload["active"]:
                context["active_saved_view_id"] = view.id
            context["saved_views"].append(payload)
        return context

    async def saved_views_list(self, request: Request) -> Response:
        """``GET /{model}/saved-views``: the current user's views on this model, as JSON."""
        await self._check_permission(request, "view")
        user_key = self._saved_views_user(request)
        views = await self._saved_views.list_for(user_key, self._model_name_lower)
        return JSONResponse({"views": [self._saved_view_payload(request, v) for v in views]})

    async def saved_view_create(self, request: Request) -> Response:
        """``POST /{model}/saved-views``: save ``name`` + ``querystring`` for the current user.

        The form fields are ``name`` and ``querystring`` (the latter defaults to
        the request's own querystring, so a sidebar form posted from the
        filtered list saves what is on screen). A browser or HTMX client is
        sent to the new view (``303`` / ``HX-Redirect``); an API client gets
        the view as ``201`` JSON. A taken name is ``409``, a blank one ``422``.
        """
        await self._check_permission(request, "view")
        user_key = self._saved_views_user(request)
        form = await request.form()
        querystring = form.get("querystring")
        if querystring is None:
            querystring = request.url.query
        try:
            view = await self._saved_views.create(
                user_key, self._model_name_lower, form.get("name"), querystring
            )
        except SavedViewNameTakenError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        href = self._saved_view_href(request, view)
        if request.headers.get("hx-request"):
            return Response(status_code=204, headers={"HX-Redirect": href})
        if wants_html(request):
            return RedirectResponse(url=href, status_code=303)
        return JSONResponse(self._saved_view_payload(request, view), status_code=201)

    async def saved_view_delete(self, request: Request, view_id: int) -> Response:
        """``DELETE /{model}/saved-views/{id}``: remove the user's own view; others' ids are 404."""
        await self._check_permission(request, "view")
        user_key = self._saved_views_user(request)
        if not await self._saved_views.delete(user_key, self._model_name_lower, view_id):
            raise HTTPException(status_code=404, detail="Saved view not found")
        # An empty 200 lets an ``hx-swap="outerHTML"`` row remove itself; API
        # clients get the conventional 204.
        return Response(status_code=200 if request.headers.get("hx-request") else 204)
