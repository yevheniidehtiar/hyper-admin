"""Update form rendering, submission and deletion."""

import logging
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse, Response

from hyperadmin.core.display import get_display_name
from hyperadmin.views.dynamic.helpers import (
    _integrity_error_to_field_errors,
    _request_scoped,
)
from hyperadmin.views.dynamic.inline import InlineViewMixin
from hyperadmin.views.dynamic.relations import RelationViewMixin
from hyperadmin.views.forms import (
    InlineFormset,
    PydanticForm,
)
from hyperadmin.views.htmx import HtmxTemplateResponse
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class UpdateViewMixin(RelationViewMixin, InlineViewMixin):
    """Update form rendering, submission and deletion."""

    @_request_scoped
    async def update_form_view(
        self,
        request: Request,
        item_id: Any,
        values: dict | None = None,
        errors: dict | None = None,
        status_code: int = 200,
        inline_formsets: list[InlineFormset] | None = None,
    ):
        """Renders the update form, optionally pre-filled with submitted values and errors."""
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "change")
        item = await self._get_or_404(pk)
        await self._check_object_permission(request, item, "change")

        initial_values = self._stored_values(item)

        # Override with re-submitted values on validation failure
        if values:
            initial_values.update(values)

        # Sensitive fields are write-only: never render their stored value.
        initial_values = self._without_sensitive(initial_values)
        if values:
            values = self._without_sensitive(values)

        relation_widgets = await self._build_relation_widgets(
            request=request, field_names=self.form_include or [], selected_values=initial_values
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=self.form_include,
            exclude=self._opaque_sensitive_fields or None,
            initial=initial_values,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
            **self._form_pk_kwargs(create=False),
        )

        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        # Build inline formsets from existing related data if not provided
        inlines_cfg = getattr(self.options, "inlines", [])
        if inline_formsets is None and inlines_cfg:
            existing_data: dict[str, list[Any]] = {}
            for spec in getattr(self.options, "inlines", []):
                prefix = spec.model_name
                related = await self.adapter.get_related(pk=pk, field=spec.relationship_name)
                if related:
                    existing_data[prefix] = list(related)
            inline_formsets = self._build_inline_formsets(existing_data, request=request)

        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "item": item,
            "item_name": get_display_name(item),
            "form": form,
            "values": values or initial_values,
            "errors": errors or {},
            "inline_formsets": inline_formsets or [],
            # Legacy keys for compatibility
            "fields": list(self.model.model_fields.keys()),
        }
        template_name = self._get_template_name("update")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
            status_code=status_code,
        )

    @_request_scoped
    async def update_view(self, request: Request, item_id: Any):
        """Handles form submission for updating an item."""
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "change")
        existing = await self._get_or_404(pk)
        await self._check_object_permission(request, existing, "change")
        form_data = await request.form()

        relation_widgets = await self._build_relation_widgets(
            request=request,
            field_names=self.form_include or [],
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=self.form_include,
            exclude=self._opaque_sensitive_fields or None,
            # The stored values let an untouched datetime keep its exact value.
            initial=self._without_sensitive(self._stored_values(existing)),
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
            **self._form_pk_kwargs(create=False),
            **self._form_datetime_kwargs(request),
        )
        data = self._extract_form_data(form_data, form)
        file_uploads = self._pop_file_uploads(data, form)
        self._keep_stored_secrets(data, existing)
        # The pk is not an input on the edit form: a natural key must still
        # validate, so it is seeded from the stored row (and dropped again below).
        data.setdefault(self.pk.attr, self.pk.value_of(existing))

        form.bind(data)
        instance, errs = form.validate(data)

        # Build inline formsets and extract/validate their data
        inline_formsets: list[InlineFormset] = []
        inline_valid_data: list[tuple[InlineFormset, list[dict]]] = []
        has_inline_errors = False
        for spec in getattr(self.options, "inlines", []):
            formset = self._inline_formset(spec)
            rows_data = formset.extract_submitted_data(form_data)
            await self._keep_stored_inline_secrets(formset, rows_data, pk)
            valid_rows, row_errors = formset.validate_rows(rows_data, parent_pk=pk)
            if row_errors:
                has_inline_errors = True
                formset.rebuild_from_submitted(form_data)
            inline_formsets.append(formset)
            inline_valid_data.append((formset, valid_rows))

        if errs or has_inline_errors:
            legacy_errs = {k: v[0] for k, v in errs.items() if v} if errs else {}
            for formset in inline_formsets:
                if not formset.errors:
                    formset.rebuild_from_submitted(form_data)
            return await self.update_form_view(
                request,
                item_id=pk,
                values=data,
                errors=legacy_errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        if not instance:
            return await self.update_form_view(
                request, item_id=pk, values=data, errors={}, status_code=422
            )

        # Ownership and inline-model permissions are checked before any write.
        await self._authorize_inline_rows(request, inline_valid_data, parent_pk=pk)

        # References must point at rows the target admin's get_queryset exposes.
        hidden_refs = await self._hidden_reference_errors(instance.model_dump(exclude_none=True))
        if hidden_refs:
            return await self.update_form_view(
                request, item_id=pk, values=data, errors=hidden_refs, status_code=422
            )

        # The pk is immutable: never write it, not even a default_factory value
        # (a fresh uuid4) that validation filled in. Auto-now fields are not
        # rendered; validation re-ran their default factory, so writing them
        # would overwrite the stored timestamp on every edit.
        try:
            update_data = instance.model_dump(
                exclude_none=True, exclude=set(form.auto_now_field_names)
            )
            update_data.pop(self.pk.attr, None)
            update_data.update(file_uploads)
            await self.adapter.update(pk=pk, data=update_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during update")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.update_form_view(
                request, item_id=pk, values=data, errors=field_errors, status_code=422
            )

        # Save inline rows
        await self._save_inline_rows(inline_valid_data, pk)

        redirect_url = admin_url_for(request, f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)

    @_request_scoped
    async def delete_action(self, request: Request, item_id: Any):
        """Deletes an item."""
        pk = self._resolve_pk(item_id)
        await self._check_permission(request, "delete")
        item = await self._get_or_404(pk)

        await self._check_object_permission(request, item, "delete")

        file_paths = self._collect_file_paths(item)
        try:
            await self.adapter.delete(pk=pk)
        except IntegrityError:
            # Still referenced by other rows (FK RESTRICT / NO ACTION); nothing was deleted.
            logger.info("Delete of %s %s blocked by referencing rows", self.model.__name__, pk)
            raise HTTPException(
                status_code=409,
                detail=f"This {self.model.__name__} cannot be deleted: other records still "
                "reference it.",
            ) from None
        self._remove_files(file_paths)

        redirect_url = admin_url_for(request, f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)
