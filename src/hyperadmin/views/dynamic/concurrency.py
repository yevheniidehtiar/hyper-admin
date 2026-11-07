"""Optimistic-concurrency helpers for the update and inline-save views.

Reads the ``__version`` token a form posted, and turns a
:class:`~hyperadmin.core.concurrency.StaleRecordError` into the HTTP 409 response
(conflict dialog, inline stale cell, or JSON). See ``docs/specs/realtime-occ.md``.
"""

from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse, Response

from hyperadmin.core.concurrency import StaleRecordError
from hyperadmin.views.dynamic.form_data import FormDataMixin
from hyperadmin.views.template_filters import ha_dom_token
from hyperadmin.views.urls import admin_url_for

VERSION_PARAM = "__version"
#: Element the edit page reserves for the conflict dialog (``update.html``).
CONFLICT_TARGET = "#ha-occ-conflict"


def version_token(value: Any) -> str:
    """Render a stored version as the string a form round-trips."""
    return value.isoformat() if isinstance(value, datetime) else str(value)


class ConcurrencyViewMixin(FormDataMixin):
    """``__version`` handling and 409 rendering for OCC-enforced models."""

    #: ``HYPERADMIN_OCC_RENDER_DIALOG``: ``False`` answers a stale save with JSON.
    occ_render_dialog: bool = True

    @property
    def _version_field(self) -> str | None:
        """The adapter's concurrency field; adapters that pre-date OCC have none."""
        return getattr(self.adapter, "version_field", None)

    @staticmethod
    def _occ_kwargs(expected_version: str | None) -> dict[str, str]:
        """``expected_version`` as keyword arguments, only when OCC supplies one."""
        return {} if expected_version is None else {"expected_version": expected_version}

    def _occ_token(self, item: Any) -> str | None:
        """The version token to embed in the form for ``item`` (``None``: OCC off)."""
        field = self._version_field
        if field is None or item is None:
            return None
        return version_token(getattr(item, field))

    def _expected_version(self, form_data: Any) -> str | None:
        """The ``__version`` a submit carries; 400 when OCC is on and it is missing."""
        if self._version_field is None:
            return None
        token = form_data.get(VERSION_PARAM)
        if not token:
            raise HTTPException(status_code=400, detail="Missing __version")
        return str(token)

    def _stale_json(self, exc: StaleRecordError) -> Response:
        return JSONResponse(
            {"error": "stale", "current_version": version_token(exc.current)}, status_code=409
        )

    def _conflict_rows(self, submitted: dict[str, Any], current: Any) -> list[dict[str, Any]]:
        """Field-by-field comparison of the user's edits and the stored row."""
        stored = self._without_sensitive(self._stored_values(current))
        rows = []
        for name, mine in self._without_sensitive(submitted).items():
            if name == self._version_field or name not in stored:
                continue
            rows.append(
                {
                    "name": name,
                    "label": self.field_labels.get(name, name.replace("_", " ").title()),
                    "mine": mine,
                    "current": stored[name],
                    "differs": mine != stored[name],
                }
            )
        return rows

    def _conflict_response(
        self,
        request: Request,
        exc: StaleRecordError,
        submitted: dict[str, Any],
        current: Any,
        item_id: Any,
    ) -> Response:
        """409 for a stale full-form save: the conflict dialog, or JSON for API clients."""
        if not self.occ_render_dialog:
            return self._stale_json(exc)
        edit_url = admin_url_for(request, f"{self._model_name_lower}-update-form", item_id=item_id)
        context = {
            "request": request,
            "model_name": self.model.__name__,
            "item_id": item_id,
            "rows": self._conflict_rows(submitted, current),
            "current_version": version_token(exc.current),
            "update_url": admin_url_for(
                request, f"{self._model_name_lower}-update", item_id=item_id
            ),
            "edit_url": str(edit_url),
        }
        return self.templates.TemplateResponse(
            request,
            "components/conflict_dialog.html",
            context,
            status_code=409,
            headers={"HX-Retarget": CONFLICT_TARGET, "HX-Reswap": "innerHTML"},
        )

    def _stale_cell_response(
        self, request: Request, exc: StaleRecordError, current: Any, field: str
    ) -> Response:
        """409 for a stale inline save: the cell re-renders the current value, marked stale."""
        if not self.occ_render_dialog:
            return self._stale_json(exc)
        item_token = ha_dom_token(self.pk.value_of(current))
        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "item": current,
            "field": field,
        }
        return self.templates.TemplateResponse(
            request,
            "components/inline_cell_stale.html",
            context,
            status_code=409,
            headers={
                "HX-Retarget": f"#cell-{self._model_name_lower}-{item_token}-{field}",
                "HX-Reswap": "outerHTML",
            },
        )
