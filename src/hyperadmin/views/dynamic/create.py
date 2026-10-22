"""Create form rendering and submission."""

import logging

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse, Response

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


class CreateViewMixin(RelationViewMixin, InlineViewMixin):
    """Create form rendering and submission."""

    @_request_scoped
    async def create_form_view(
        self,
        request: Request,
        values: dict | None = None,
        errors: dict | None = None,
        status_code: int = 200,
        inline_formsets: list[InlineFormset] | None = None,
    ):
        """Renders the create form.

        For HTMX requests, only the inner form body is returned to prevent nesting the full page
        into the target container.
        """
        await self._check_permission(request, "add")
        # Build a Pydantic-backed form abstraction for templates
        # Create forms exclude form_create_exclude fields (e.g. updated_at)
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(
            request=request, field_names=create_include or [], selected_values=values
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=create_include,
            exclude=self.form_create_exclude,
            initial=values or {},
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
            **self._form_pk_kwargs(create=True),
        )
        if errors:
            form.bind(values or {})
            norm_errors = {k: (v if isinstance(v, list) else [v]) for k, v in errors.items()}
            form.errors = norm_errors
            for f in form.fields:
                f.errors = norm_errors.get(f.name)

        # Build inline formsets if not provided (e.g. on first render)
        inlines_cfg = getattr(self.options, "inlines", [])
        if inline_formsets is None and inlines_cfg:
            inline_formsets = self._build_inline_formsets(request=request)

        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "form": form,
            "values": values or {},
            "errors": errors or {},
            "inline_formsets": inline_formsets or [],
        }
        template_name = self._get_template_name("create")
        return HtmxTemplateResponse(self.templates).render(
            template_name=template_name,
            context=context,
            request=request,
            block="form_body",
            status_code=status_code,
        )

    @_request_scoped
    async def create_view(self, request: Request):
        """Handles form submission for creating a new item."""
        await self._check_permission(request, "add")
        form_data = await request.form()

        # Use PydanticForm for consistent binding/validation
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(
            request=request,
            field_names=create_include or [],
        )
        form = PydanticForm(
            self.model,
            widgets=relation_widgets,
            include=create_include,
            exclude=self.form_create_exclude,
            fieldsets=getattr(self.options, "fieldsets", None) or None,
            form_layout=getattr(self.options, "form_layout", None),
            form_fields=getattr(self.options, "form_fields", None) or None,
            **self._form_pk_kwargs(create=True),
            **self._form_datetime_kwargs(request),
        )
        data = self._extract_form_data(form_data, form)
        file_uploads = self._pop_file_uploads(data, form)
        form.bind(data)
        instance, errs = form.validate(data)

        inline_formsets, inline_valid_data, has_inline_errors = self._validate_inline_formsets(
            form_data
        )

        if errs or has_inline_errors:
            legacy_errs = {k: v[0] for k, v in errs.items() if v} if errs else {}
            # Rebuild inline formsets from submitted data for re-rendering
            for formset in inline_formsets:
                if not formset.errors:
                    formset.rebuild_from_submitted(form_data)
            return await self.create_form_view(
                request,
                values=data,
                errors=legacy_errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        if not instance:
            return await self.create_form_view(
                request,
                values=data,
                errors=errs,
                status_code=422,
                inline_formsets=inline_formsets,
            )

        # A new parent owns no children yet: any submitted child pk is foreign.
        await self._authorize_inline_rows(request, inline_valid_data, parent_pk=None)

        # References must point at rows the target admin's get_queryset exposes.
        hidden_refs = await self._hidden_reference_errors(instance.model_dump())
        if hidden_refs:
            return await self.create_form_view(
                request, values=data, errors=hidden_refs, status_code=422
            )

        try:
            # Auto-now fields are stamped by the model/database, never the form.
            create_data = instance.model_dump(exclude=set(form.auto_now_field_names))
            create_data.update(file_uploads)
            new_item = await self.adapter.create(data=create_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during create")
            field_errors = _integrity_error_to_field_errors(exc)
            return await self.create_form_view(
                request, values=data, errors=field_errors, status_code=422
            )

        # Save inline rows with the parent PK (``0`` and ``""`` are valid keys).
        parent_pk = self.pk.value_of(new_item)
        if parent_pk is not None:
            await self._save_inline_rows(inline_valid_data, parent_pk)
            redirect_url = admin_url_for(
                request, f"{self.model.__name__.lower()}-detail", item_id=parent_pk
            )
        else:
            redirect_url = admin_url_for(request, f"{self.model.__name__.lower()}-list")

        if "hx-request" in request.headers:
            return Response(status_code=200, headers={"HX-Redirect": str(redirect_url)})

        return RedirectResponse(url=redirect_url, status_code=303)
