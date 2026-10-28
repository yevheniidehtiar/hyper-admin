"""Inline formsets and inline (in-list) editing."""

import logging
from typing import Any

from fastapi import HTTPException, Query, Request
from starlette.responses import Response

from hyperadmin.core.adapters import (
    InlineRowNotOwnedError,
    scoped_queryset_filters,
)
from hyperadmin.core.primary_key import InvalidPrimaryKey
from hyperadmin.core.schema import dump_instance, schema_for
from hyperadmin.core.sensitive import (
    is_text_annotation,
)
from hyperadmin.views.dynamic.form_data import FormDataMixin
from hyperadmin.views.dynamic.helpers import (
    _request_scoped,
)
from hyperadmin.views.forms import (
    CheckboxInput,
    InlineFormset,
    PydanticForm,
)

logger = logging.getLogger(__name__)


class InlineViewMixin(FormDataMixin):
    """Inline formsets and inline (in-list) editing."""

    async def _save_inline_rows(
        self,
        inline_valid_data: list[tuple[InlineFormset, list[dict]]],
        parent_pk: Any,
    ) -> None:
        """Persist validated inline rows — create, update, or delete as needed."""
        try:
            for formset, rows in inline_valid_data:
                await self.adapter.save_inline_rows(formset.spec, rows, parent_pk)
        except InlineRowNotOwnedError as exc:
            raise HTTPException(status_code=404, detail="Inline row not found") from exc

    async def _keep_stored_inline_secrets(
        self, formset: InlineFormset, rows: list[dict[str, Any]], parent_pk: Any
    ) -> None:
        """Write-only semantics for sensitive inline fields on existing rows.

        Inline rows never render a stored secret, so an empty submitted value on
        an existing child keeps the stored one (a non-text sensitive field always
        keeps it). Rows that are not children of ``parent_pk`` are left as
        submitted; the ownership check rejects them before any write.
        """
        sensitive = [f for f in formset.display_fields if f in formset.sensitive_fields]
        existing_rows = [r for r in rows if r.get("_pk") is not None and not r.get("_delete")]
        if not sensitive or not existing_rows:
            return
        related = await self.adapter.get_related(pk=parent_pk, field=formset.spec.relationship_name)
        child_pk = self.adapter.for_model(formset.spec.model).pk
        by_pk = {child_pk.value_of(child): child for child in related or []}
        model_fields = schema_for(formset.spec.model).model_fields
        for row in existing_rows:
            try:
                child = by_pk.get(child_pk.parse(row["_pk"]))
            except InvalidPrimaryKey:
                child = None
            if child is None:
                continue
            for name in sensitive:
                info = model_fields.get(name)
                opaque = info is not None and not is_text_annotation(info.annotation)
                if opaque or row.get(name) in (None, ""):
                    row[name] = getattr(child, name, None)

    def _many_to_one_targets(self) -> dict[str, Any]:
        """Map each local FK column of a many-to-one relationship to its target class."""
        inspector = getattr(self.adapter, "inspector", None)
        targets: dict[str, Any] = {}
        if not inspector:
            return targets
        for rel in inspector.relationships:
            if getattr(getattr(rel, "direction", None), "name", "") != "MANYTOONE":
                continue
            target = getattr(getattr(rel, "mapper", None), "class_", None)
            for col in getattr(rel, "local_columns", []):
                key = getattr(col, "key", None) or getattr(col, "name", None)
                if key and target is not None:
                    targets[key] = target
        return targets

    async def _hidden_reference_errors(self, data: dict[str, Any]) -> dict[str, str]:
        """Return a field error for each FK value the target admin's queryset hides.

        The edit form and the choices endpoint never offer such rows, but a
        crafted POST/PUT could still submit their key. Only targets with active
        row scoping need the lookup; the database FK constraint covers the rest.
        """
        errors: dict[str, str] = {}
        for name, target in self._many_to_one_targets().items():
            value = data.get(name)
            if value in (None, "") or not scoped_queryset_filters(target):
                continue
            # Via for_model(), not a bare adapter_registry lookup + self.adapter.engine:
            # a session_factory=-only admin has no engine, and the bare construction
            # would raise ValueError (SDD C.3).
            target_adapter = self.adapter.for_model(target)
            if await target_adapter.get(pk=value) is None:
                errors[name] = "Select a valid choice."
        return errors

    async def _authorize_inline_rows(
        self,
        request: Request,
        inline_valid_data: list[tuple[InlineFormset, list[dict]]],
        parent_pk: Any,
    ) -> None:
        """Reject foreign child rows (404) and rows the user may not write (403).

        Runs before any write. A submitted ``<prefix>-<i>-pk`` is never trusted
        on its own: it must be an existing child of ``parent_pk`` (``None`` for a
        parent being created, which owns no rows). Each row also needs the
        inline model's own ``add`` / ``change`` / ``delete`` permission when that
        model is registered (see :meth:`_is_registered`).
        """
        for formset, rows in inline_valid_data:
            try:
                await self.adapter.ensure_inline_rows_owned(formset.spec, rows, parent_pk)
            except InlineRowNotOwnedError as exc:
                raise HTTPException(status_code=404, detail="Inline row not found") from exc
            if not self._is_registered(formset.spec.model):
                # An unregistered inline model has no permission rows that could
                # ever be granted: the parent's add/change check (made by the
                # calling handler) governs its rows.
                continue
            needed: set[str] = set()
            for row in rows:
                if row.get("_delete"):
                    needed.add("delete")
                elif row.get("_pk") is not None:
                    needed.add("change")
                else:
                    needed.add("add")
            for verb in sorted(needed):
                await self._check_permission(request, verb, model_name=formset.spec.model_name)

    @_request_scoped
    async def inline_add_row_view(
        self,
        request: Request,
        inline_prefix: str,
        index: int = 0,
    ) -> Response:
        """HTMX endpoint: returns a single inline row HTML fragment.

        GET /{model_name}/inline/{inline_prefix}/add-row?index=N
        """
        await self._check_any_permission(request, ("add", "change"))
        spec = None
        for s in getattr(self.options, "inlines", []):
            if s.model_name == inline_prefix:
                spec = s
                break
        if spec is None:
            raise HTTPException(status_code=404, detail=f"Unknown inline: {inline_prefix!r}")

        formset = self._inline_formset(spec)
        row = formset._build_row(index)
        context = {"request": request, "pk_attr": self.pk.attr, "row": row, "inline": formset}
        template = self.templates.get_template("components/inline_row.html")
        html = template.render(context)
        return Response(content=html, media_type="text/html")

    def _is_inline_editable(self, field: str) -> bool:
        """Return True if ``field`` is in the list_editable allow-list and on the schema.

        The primary key is never editable inline.
        """
        if field in self.pk.attrs:
            return False
        if field not in schema_for(self.model).model_fields:
            return False
        return field in (self.options.list_editable or [])

    @_request_scoped
    async def inline_edit_form_view(
        self,
        request: Request,
        item_id: Any,
        field: str,
        cancel: int = Query(0),
    ):
        """Renders the inline editor fragment for a single editable cell.

        ``?cancel=1`` returns the static cell instead — used by the Cancel
        button in the editor to restore the read-only view without hitting
        a separate endpoint.
        """
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "change")
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "change")

        if cancel:
            context = {
                "request": request,
                "pk_attr": self.pk.attr,
                "model_name": self.model.__name__,
                "item": item,
                "field": field,
                "saved": False,
            }
            return self.templates.TemplateResponse(request, "components/inline_cell.html", context)

        # Build a single-field form so we reuse widget selection + validation
        form = PydanticForm(
            self.model,
            include=[field],
            initial={field: getattr(item, field)},
            pk_attr=self.pk.attr,
        )
        form_field = next((f for f in form.fields if f.name == field), None)
        if form_field is None:
            # Field is not exposed by PydanticForm (e.g. auto-now / id) — treat as not editable
            raise HTTPException(status_code=403, detail="Field not editable")

        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "item": item,
            "field": field,
            "form_field": form_field,
            "form": form,
        }
        return self.templates.TemplateResponse(request, "components/inline_editor.html", context)

    @_request_scoped
    async def inline_save_view(self, request: Request, item_id: Any, field: str):
        """Validates and persists a single field for ``item_id``."""
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "change")
        if not self._is_inline_editable(field):
            raise HTTPException(status_code=403, detail="Field not editable")

        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "change")

        form_data = await request.form()
        raw_value: Any = form_data.get(field)

        # Reuse the full-model PydanticForm to keep validation rules consistent
        # with the per-row update form. We seed it with the current row dump
        # and only override the edited field — ensures min_length/required etc.
        # apply identically.
        current = dump_instance(item)
        merged = dict(current)
        merged[field] = raw_value

        form = PydanticForm(
            self.model,
            initial=current,
            pk_attr=self.pk.attr,
            **self._form_datetime_kwargs(request),
        )
        form_field = next((f for f in form.fields if f.name == field), None)
        if form_field is None:
            raise HTTPException(status_code=403, detail="Field not editable")

        # Unchecked checkbox semantics: bool fields with no value submitted → False
        if isinstance(form_field.widget, CheckboxInput) and field not in form_data:
            merged[field] = False

        instance, errs = form.validate(merged)
        field_errors = errs.get(field) if errs else None
        if field_errors:
            error_form_field = next((f for f in form.fields if f.name == field), None)
            if error_form_field is not None:
                error_form_field.value = raw_value
                error_form_field.errors = field_errors
            context = {
                "request": request,
                "pk_attr": self.pk.attr,
                "model_name": self.model.__name__,
                "item": item,
                "field": field,
                "form_field": error_form_field,
                "errors": field_errors,
                "current_value": getattr(item, field),
            }
            return self.templates.TemplateResponse(
                request, "components/inline_cell_error.html", context, status_code=422
            )

        if not instance:
            # Validation failed for a *different* field; we still reject the save.
            return self.templates.TemplateResponse(
                request,
                "components/inline_cell_error.html",
                {
                    "request": request,
                    "pk_attr": self.pk.attr,
                    "model_name": self.model.__name__,
                    "item": item,
                    "field": field,
                    "form_field": form_field,
                    "errors": ["Invalid value"],
                    "current_value": getattr(item, field),
                },
                status_code=422,
            )

        # Persist only the edited field — exclude_unset would also work, but
        # we know precisely what changed.
        new_value = getattr(instance, field)
        await self.adapter.update(pk=pk, data={field: new_value})

        # Re-fetch to get the canonical stored value (e.g. type coercion)
        refreshed = await self.adapter.get(pk=pk)
        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "item": refreshed,
            "field": field,
            "options": self.options,
            "saved": True,
        }
        # Announce save via aria-live region using an HX-Trigger event.
        # OOB swaps are avoided here because they don't compose cleanly when
        # the primary swap target is a single <td> element.
        response = self.templates.TemplateResponse(request, "components/inline_cell.html", context)
        response.headers["HX-Trigger-After-Swap"] = (
            '{"hyperadmin:cell-saved": {"field": "' + field + '"}}'
        )
        return response
