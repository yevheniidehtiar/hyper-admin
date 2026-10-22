"""Custom row actions and bulk actions."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import HTTPException, Request
from pydantic import ValidationError
from starlette.responses import RedirectResponse, Response

from hyperadmin.core.actions import ActionDef
from hyperadmin.core.bulk_results import BulkRowResult, BulkRowStatus
from hyperadmin.core.primary_key import InvalidPrimaryKey, PrimaryKeyInfo
from hyperadmin.i18n import translate_error
from hyperadmin.views.dynamic.base import DynamicModelViewBase
from hyperadmin.views.dynamic.helpers import (
    _request_scoped,
)
from hyperadmin.views.forms import (
    field_is_required,
)
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class ActionViewMixin(DynamicModelViewBase):
    """Custom row actions and bulk actions."""

    @_request_scoped
    async def run_action(self, request: Request, item_id: Any, action_name: str) -> Response:
        """Dispatch a custom action registered via ``@action`` on the ModelAdmin.

        POST /{model_name}/{item_id}/action/{action_name}

        Returns an HTMX redirect to the model list on success, or delegates to the
        handler's return value when it returns a :class:`starlette.responses.Response`.
        The handler receives the typed key (still an ``int`` for int-id models).
        """
        pk = self._resolve_pk(item_id)
        action_def = self._action_map.get(action_name)
        if action_def is None:
            raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")

        await self._check_permission(request, f"action_{action_name}")
        # Load under the queryset scope (404 for hidden rows) and re-check per object.
        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, f"action_{action_name}")

        result = await action_def.handler(self._admin_instance, request, pk)

        if isinstance(result, Response):
            return result

        redirect_url = admin_url_for(request, f"{self._model_name_lower}-list")
        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})
        return RedirectResponse(url=redirect_url, status_code=303)

    def _resolve_bulk_action(self, action_name: str) -> ActionDef:
        """Return the bulk ``ActionDef`` for ``action_name`` or raise 404."""
        action_def = self._action_map.get(action_name)
        if action_def is None or not action_def.bulk:
            raise HTTPException(status_code=404, detail=f"Bulk action '{action_name}' not found")
        return action_def

    @staticmethod
    def _parse_ids(form: Any, pk: PrimaryKeyInfo) -> list[Any]:
        """Parse the ``ids`` multi-valued form field into typed keys via ``pk.parse``.

        Silently drops entries that aren't valid keys — those would not match
        any row anyway.
        """
        raw = form.getlist("ids") if hasattr(form, "getlist") else []
        parsed: list[Any] = []
        for value in raw:
            # Per-value tolerance: silently skip any id that isn't a valid key.
            try:
                parsed.append(pk.parse(value))
            except InvalidPrimaryKey:  # noqa: PERF203
                continue
        return parsed

    async def _execute_bulk(
        self,
        request: Request,
        action_def: ActionDef,
        ids: list[Any],
        params: Any | None,
    ) -> list[BulkRowResult]:
        """Run ``action_def.handler`` over ``ids`` with per-row outcome capture.

        Each row is wrapped in object-permission re-check + exception capture so
        a single failure cannot abort the whole bulk run.
        """
        outcomes: list[BulkRowResult] = []
        permission_codename = f"action_{action_def.name}"
        for item_id in ids:
            try:
                item = await self.adapter.get(pk=item_id)
            except Exception:
                # Never echo the raw exception: driver errors embed SQL and bound
                # parameters. Details go to the server log only.
                logger.exception("Bulk action %r could not load row %s", action_def.name, item_id)
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail="Database error"))
                continue
            if item is None:
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail="not found"))
                continue
            try:
                await self._check_object_permission(request, item, permission_codename)
            except HTTPException as exc:
                outcomes.append(
                    BulkRowResult(id=item_id, status="forbidden", detail=str(exc.detail))
                )
                continue
            try:
                await action_def.handler(self._admin_instance, request, item_id, params=params)
            except HTTPException as exc:
                status: BulkRowStatus = (
                    "forbidden" if exc.status_code == HTTPStatus.FORBIDDEN else "failed"
                )
                outcomes.append(BulkRowResult(id=item_id, status=status, detail=str(exc.detail)))
            except Exception:
                logger.exception("Bulk action %r failed on row %s", action_def.name, item_id)
                outcomes.append(BulkRowResult(id=item_id, status="failed", detail="Action failed"))
            else:
                outcomes.append(BulkRowResult(id=item_id, status="ok", detail=None))
        return outcomes

    def _render_bulk_result(
        self,
        request: Request,
        action_def: ActionDef,
        outcomes: list[BulkRowResult],
    ) -> Response:
        """Render the per-row result page (or HTMX fragment)."""
        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "action": action_def,
            "outcomes": outcomes,
            "model_name": self._model_name_lower,
            "bulk_endpoint_url": admin_url_for(
                request, f"{self._model_name_lower}-bulk-action", action_name=action_def.name
            ),
            "failed_ids": [self.pk.to_str(o.id) for o in outcomes if o.status != "ok"],
        }
        if "hx-request" in request.headers:
            # Fragment for the list's result region (the toolbar's hx-target).
            context["is_htmx"] = True
            return self.templates.TemplateResponse(request, "components/bulk_result.html", context)
        context["is_htmx"] = False
        return self.templates.TemplateResponse(request, "bulk_result.html", context)

    def _render_bulk_form(
        self,
        request: Request,
        action_def: ActionDef,
        ids: list[Any],
        errors: dict[str, list[str]] | None = None,
    ) -> Response:
        """Render the Pydantic-derived parameter form before bulk execution."""
        form_model = action_def.form
        fields: list[dict[str, Any]] = []
        if form_model is not None:
            for name, info in form_model.model_fields.items():
                fields.append(
                    {
                        "name": name,
                        "label": info.title or name.replace("_", " ").capitalize(),
                        "required": field_is_required(info),
                        "input_type": "number" if info.annotation is int else "text",
                        "errors": (errors or {}).get(name, []),
                    }
                )
        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "action": action_def,
            "ids": [self.pk.to_str(pk) for pk in ids],
            "fields": fields,
            "model_name": self._model_name_lower,
            "confirm_url": admin_url_for(
                request,
                f"{self._model_name_lower}-bulk-action-confirm",
                action_name=action_def.name,
            ),
        }
        if "hx-request" in request.headers:
            # The parameter step is a dialog: retarget the toolbar's (or the
            # confirm form's) swap from the result region into the popup slot.
            context["is_htmx"] = True
            return self.templates.TemplateResponse(
                request,
                "components/bulk_form.html",
                context,
                headers={"HX-Retarget": "#ha-popup-root", "HX-Reswap": "innerHTML"},
            )
        context["is_htmx"] = False
        return self.templates.TemplateResponse(request, "bulk_form.html", context)

    @_request_scoped
    async def run_bulk_action(self, request: Request, action_name: str) -> Response:
        """Entry point for bulk actions.

        ``POST /{model}/actions/{name}/bulk``

        - When the action declares a Pydantic ``form``, this endpoint renders the
          parameter-collection form with the selected ids preserved.
        - Otherwise it executes the handler per row and renders the per-row
          result page.
        """
        action_def = self._resolve_bulk_action(action_name)
        await self._check_permission(request, f"action_{action_name}")

        form = await request.form()
        ids = self._parse_ids(form, self.pk)

        if action_def.requires_selection and not ids:
            raise HTTPException(status_code=400, detail="Selection required")

        if action_def.form is not None:
            return self._render_bulk_form(request, action_def, ids)

        outcomes = await self._execute_bulk(request, action_def, ids, params=None)
        return self._render_bulk_result(request, action_def, outcomes)

    @_request_scoped
    async def confirm_bulk_action(self, request: Request, action_name: str) -> Response:
        """Validate the Pydantic param form and execute the bulk handler.

        ``POST /{model}/actions/{name}/bulk/confirm``
        """
        action_def = self._resolve_bulk_action(action_name)
        await self._check_permission(request, f"action_{action_name}")

        if action_def.form is None:
            raise HTTPException(
                status_code=404, detail=f"Bulk action '{action_name}' has no confirm step"
            )

        form = await request.form()
        ids = self._parse_ids(form, self.pk)

        if action_def.requires_selection and not ids:
            raise HTTPException(status_code=400, detail="Selection required")

        form_model = action_def.form
        payload = {key: value for key, value in form.items() if key != "ids"}
        try:
            params = form_model(**payload)
        except ValidationError as exc:
            errors: dict[str, list[str]] = {}
            for err in exc.errors():
                loc = err.get("loc") or ("__all__",)
                field = str(loc[0])
                errors.setdefault(field, []).append(translate_error(err))
            return self._render_bulk_form(request, action_def, ids, errors=errors)

        outcomes = await self._execute_bulk(request, action_def, ids, params=params)
        return self._render_bulk_result(request, action_def, outcomes)
