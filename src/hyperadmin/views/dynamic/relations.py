"""Relation widgets, choices, autocomplete and the create popup."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError
from starlette.responses import Response

from hyperadmin.core.choices import ChoiceItem, SelectFieldMeta
from hyperadmin.core.display import get_display_name
from hyperadmin.core.fields import classify_field
from hyperadmin.core.registry import site
from hyperadmin.views.dynamic.form_data import FormDataMixin
from hyperadmin.views.dynamic.helpers import (
    _MAX_CHOICES_LIMIT,
    _integrity_error_to_field_errors,
    _request_scoped,
)
from hyperadmin.views.forms import (
    HtmxWidget,
    PydanticForm,
    relation_widget,
)
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class RelationViewMixin(FormDataMixin):
    """Relation widgets, choices, autocomplete and the create popup."""

    async def _build_relation_widgets(
        self,
        field_names: list[str],
        selected_values: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> dict[str, HtmxWidget]:
        """Return a widget override dict for relation fields detected by classify_field().

        For each field in *field_names* that resolves to a relation, this method
        either pre-fetches choices (preload=True) or creates a lazy HTMX widget
        (preload=False) pointing at the choices endpoint for that field.

        When the user may not view the target model, no target row is fetched:
        the widget only carries the currently selected key(s), labelled
        ``"<Model> (<pk>)"``, so saving the form keeps the stored value.
        """
        widgets: dict[str, HtmxWidget] = {}
        sv = selected_values or {}
        dependent_fields: dict[str, str] = getattr(self.options, "dependent_fields", {})
        relation_filters = getattr(self.options, "relation_filters", None) or {}
        autocomplete = bool(getattr(self.options, "use_autocomplete_widget", False))

        # FK-column → relationship-name mapping so that country_id → "country"
        # for get_choices() and the HTMX URL.
        fk_to_rel = self._fk_to_relation()

        for name, field_info in self.model.model_fields.items():
            if field_names and name not in field_names:
                continue
            raw_meta = classify_field(field_info, self.model)
            if not isinstance(raw_meta, SelectFieldMeta):
                continue
            if raw_meta.choices_source != "relation":
                continue
            meta = raw_meta
            # Resolve FK column name to relationship name (e.g. country_id → country)
            rel_name: str = fk_to_rel.get(name) or name
            choices_url = f"/{self._model_name_lower}/choices/{rel_name}"
            dependency = relation_filters.get(name)
            dependent_on = (
                meta.dependent_on
                or dependent_fields.get(name)
                or (dependency.depends_on if dependency else None)
            )
            choices: list[ChoiceItem]
            target = self._relation_target_for_field(name)
            if request is not None and not await self._may_view_related(request, target):
                choices = self._opaque_selected_choices(target, sv.get(name))
            elif meta.preload:
                choices = await self._preload_choices(name, rel_name, dependent_on, sv)
            elif autocomplete:
                # No preload: keep the stored key(s) selectable until the user searches.
                choices = self._opaque_selected_choices(target, sv.get(name))
            else:
                choices = []
            popup_url = None
            if autocomplete and request is not None:
                choices_url = str(
                    admin_url_for(request, f"{self._model_name_lower}-choices", field_name=rel_name)
                )
                popup_url = await self._popup_url_for(request, target, name)
            widgets[name] = relation_widget(
                choices_url=choices_url,
                choices=choices,
                preload=meta.preload,
                multiple=meta.multiple,
                dependent_on=dependent_on,
                autocomplete=autocomplete,
                placeholder=dependency.placeholder if dependency else None,
                popup_url=popup_url,
            )
        return widgets

    async def _preload_choices(
        self,
        name: str,
        rel_name: str,
        dependent_on: str | None,
        selected_values: dict[str, Any],
    ) -> list[ChoiceItem]:
        """Return the preloaded options for relation field ``name``.

        Mirrors what :meth:`choices_view` returns for the same widget: a
        dependent field is filtered by the parent's current value (and
        preloads nothing while the parent is unset, so the template shows the
        placeholder), and labels follow ``AdminOptions.relation_display``.
        The stored value stays selected.
        """
        filters: dict[str, Any] = {}
        if dependent_on is not None:
            parent_value = selected_values.get(dependent_on)
            if parent_value in (None, ""):
                return []
            filters[dependent_on] = parent_value
        label_fn = self._relation_label_fn(name, rel_name)
        if label_fn is not None:
            # Only when configured: adapters predating ``label_fn`` keep working.
            filters["label_fn"] = label_fn
        raw_choices = await self.adapter.get_choices(rel_name, **filters)
        current = str(selected_values.get(name, ""))
        return [
            ChoiceItem(value=c["value"], label=c["label"], selected=c["value"] == current)
            for c in raw_choices
        ]

    def _relation_label_fn(self, name: str, rel_name: str) -> Callable[[Any], str] | None:
        """Return the ``label_fn`` for the relation widget ``name`` renders, or ``None``.

        ``relation_display`` is keyed by the form field (FK column) or by the
        relationship name; the FK column wins when both are configured.
        """
        relation_display = getattr(self.options, "relation_display", None) or {}
        display_key = next((k for k in (name, rel_name) if k in relation_display), None)
        if display_key is None:
            return None
        return functools.partial(self._resolve_relation_label, target_field=display_key)

    async def _popup_url_for(self, request: Request, target: Any, field_name: str) -> str | None:
        """Return the "+" create-popup URL for ``field_name``'s target model, or ``None``.

        Only a model registered with this Admin, whose admin exposes create and
        whose ``add`` permission the user holds, gets a popup. The URL names
        this model as ``source`` so the popup labels the created row the way
        this form's ``relation_display`` renders ``field_name``.
        """
        if target is None or target is self.model or not self._is_registered(target):
            return None
        from starlette.routing import NoMatchFound  # noqa: PLC0415

        target_name = target.__name__.lower()
        if not await self._has_permission(request, f"add_{target_name}"):
            return None
        try:
            url = admin_url_for(request, f"{target_name}-create-popup")
        except NoMatchFound:
            return None
        return str(url.include_query_params(target=field_name, source=self._model_name_lower))

    @staticmethod
    def _opaque_selected_choices(target: Any, current: Any) -> list[ChoiceItem]:
        """Choices for the selected key(s) only, labelled without reading the target row."""
        if current in (None, ""):
            return []
        values = current if isinstance(current, (list, tuple, set)) else [current]
        target_name = getattr(target, "__name__", "Item")
        return [
            ChoiceItem(value=str(v), label=f"{target_name} ({v})", selected=True)
            for v in values
            if v not in (None, "")
        ]

    @_request_scoped
    async def choices_view(
        self,
        request: Request,
        field_name: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> Response:
        """HTMX endpoint: returns an HTML `<option>` fragment for a relation field.

        GET /{model_name}/choices/{field_name}?q=&limit=50&offset=0[&{parent_field}={value}]

        Only the cascade keys declared for this relation's widget (``dependent_on``,
        ``AdminOptions.dependent_fields`` / ``relation_filters``) are forwarded as
        equality filters to ``adapter.get_choices()``; any other query parameter
        is ignored, so the endpoint is not an equality oracle on the target model.
        The target model's admin ``get_queryset`` applies through the request scope.
        """
        await self._check_permission(request, "view")
        if limit > _MAX_CHOICES_LIMIT:
            raise HTTPException(
                status_code=400, detail=f"limit {limit} exceeds maximum of {_MAX_CHOICES_LIMIT}"
            )

        # Validate that field_name is a known relation on this model
        targets = self._relation_targets()
        if field_name not in targets:
            raise HTTPException(status_code=404, detail=f"Unknown relation field: {field_name!r}")

        # Listing related rows discloses the target model: require view on it too.
        if not await self._may_view_related(request, targets[field_name]):
            raise HTTPException(status_code=403, detail="Permission denied")

        # Forward only the declared cascade keys (e.g. country_id=1)
        declared = self._declared_cascade_keys(field_name)
        extra_filters: dict[str, Any] = {
            k: v for k, v in request.query_params.items() if k in declared
        }
        ignored = set(request.query_params) - declared - {"q", "limit", "offset"}
        if ignored:
            logger.debug("Ignoring undeclared choices parameters %s", sorted(ignored))

        # relation_display is keyed by the form field (FK column or relationship name).
        relation_display = getattr(self.options, "relation_display", None) or {}
        owners = [n for n, rel in self._fk_to_relation().items() if rel == field_name]
        display_key = next((n for n in [*owners, field_name] if n in relation_display), None)
        if display_key is not None:
            # Only when configured: adapters predating ``label_fn`` keep working.
            extra_filters["label_fn"] = functools.partial(
                self._resolve_relation_label, target_field=display_key
            )
        choices = await self.adapter.get_choices(
            field_name, q=q, limit=limit, offset=offset, **extra_filters
        )
        context = {"request": request, "pk_attr": self.pk.attr, "choices": choices}
        template = self.templates.get_template("widgets/choices_options.html")
        html = template.render(context)
        return Response(content=html, media_type="text/html")

    def _resolve_relation_label(
        self, instance: Any, target_field: str, options: Any | None = None
    ) -> str:
        """Render the option label for ``instance`` per ``AdminOptions.relation_display``.

        ``options`` defaults to this admin's; the popup passes the originating
        form's admin options so the created row is labelled as that form
        renders ``target_field``. Falls back to :func:`get_display_name` (never
        the default ``__str__``, which prints every column) when no template /
        callable is configured or when rendering raises. The view never crashes
        a popup response over a cosmetic label.
        """
        relation_display = getattr(options or self.options, "relation_display", None) or {}
        template = relation_display.get(target_field)
        if template is None:
            return get_display_name(instance)
        if callable(template):
            try:
                return str(template(instance))
            except Exception:
                logger.warning(
                    "relation_display callable for %r raised; falling back to the display name",
                    target_field,
                )
                return get_display_name(instance)
        try:
            return template.format(
                **{name: getattr(instance, name, "") for name in instance.model_fields}
            )
        except Exception:
            logger.warning(
                "relation_display template %r raised; falling back to the display name",
                target_field,
            )
            return get_display_name(instance)

    @_request_scoped
    async def create_popup_view(self, request: Request) -> Response:
        """Inline-create endpoint for FK/M2M autocomplete widgets.

        GET  /{model}/create-popup?target=<field>&source=<parent model>
            Renders the popup form fragment for the modal.
        POST /{model}/create-popup?source=<parent model>
            Creates the row. On success returns 200 with an empty body and an
            ``HX-Trigger`` header carrying
            ``{"hyperadminPopupCreated": {"target": <field>, "id": <pk>, "label": <display>}}``
            so the parent widget can insert the new option and close the modal.
            ``label`` follows the ``source`` admin's ``relation_display`` for
            ``target`` — the template its preload and search results use — so
            the inserted option matches its neighbours.

        Validation failures keep the modal open by re-rendering the form
        fragment with field-level errors. Permission failures propagate through
        :meth:`_check_permission`.
        """
        await self._check_permission(request, "add")

        source = request.query_params.get("source") or None
        if request.method == "GET":
            target = request.query_params.get("target")
            if not target:
                raise HTTPException(status_code=400, detail="target query param required")
            return self._render_popup_form(request, target=target, source=source)

        form_data = await request.form()
        target_value = form_data.get("target")
        if not target_value or not isinstance(target_value, str):
            raise HTTPException(status_code=400, detail="target form field required")
        target = target_value

        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        relation_widgets = await self._build_relation_widgets(
            field_names=create_include or [], request=request
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
        data.pop("target", None)
        file_uploads = self._pop_file_uploads(data, form)
        form.bind(data)
        instance, errs = form.validate(data)

        if errs or not instance:
            legacy_errs = {k: v[0] for k, v in (errs or {}).items() if v}
            return self._render_popup_form(
                request,
                target=str(target),
                source=source,
                values=data,
                errors=legacy_errs,
                status_code=200,
            )

        try:
            # Auto-now fields are stamped by the model/database, never the form.
            create_data = instance.model_dump(exclude=set(form.auto_now_field_names))
            create_data.update(file_uploads)
            new_item = await self.adapter.create(data=create_data)
        except IntegrityError as exc:
            logger.exception("IntegrityError during popup create")
            field_errors = _integrity_error_to_field_errors(exc)
            return self._render_popup_form(
                request,
                target=str(target),
                source=source,
                values=data,
                errors=field_errors,
                status_code=200,
            )

        new_pk = self.pk.value_of(new_item)
        label = self._popup_label(new_item, str(target), source)
        payload = {
            "hyperadminPopupCreated": {
                "target": str(target),
                # int keys stay JSON numbers; UUIDs become their canonical string.
                "id": None if new_pk is None else self.pk.to_json(new_pk),
                "label": label,
            }
        }
        import json as _json  # noqa: PLC0415

        return Response(
            content="",
            status_code=200,
            headers={"HX-Trigger": _json.dumps(payload)},
        )

    def _popup_label(self, instance: Any, target: str, source: str | None) -> str:
        """Label the popup-created ``instance`` as the originating form renders ``target``.

        The option lands in the ``source`` model's form, so the label follows
        *that* admin's ``relation_display`` (keyed by the FK column ``target``
        or by its relationship name), not this model's. The source is honoured
        only when it is registered and ``target`` really relates to this model;
        otherwise the display name is used.
        """
        source_model = self._registered_model_named(source)
        if source_model is None:
            return get_display_name(instance)
        rel_name = self._source_relation_name(source_model, target)
        if rel_name is None:
            return get_display_name(instance)
        options = getattr(self._admin_for_model(source_model), "options", None)
        relation_display = getattr(options, "relation_display", None) or {}
        display_key = next((k for k in (target, rel_name) if k in relation_display), None)
        if display_key is None:
            return get_display_name(instance)
        return self._resolve_relation_label(instance, display_key, options=options)

    @staticmethod
    def _registered_model_named(slug: str | None) -> Any:
        """Return the registered model whose URL slug is ``slug`` (or ``None``)."""
        if not slug:
            return None
        return next((m for m in site._registry if m.__name__.lower() == slug), None)

    def _source_relation_name(self, source_model: Any, target: str) -> str | None:
        """Return the ``source_model`` relationship ``target`` renders when it points here."""
        from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415
        from sqlalchemy.exc import NoInspectionAvailable  # noqa: PLC0415

        try:
            mapper = sa_inspect(source_model)
        except NoInspectionAvailable:
            return None
        for rel in mapper.relationships:
            if getattr(getattr(rel, "mapper", None), "class_", None) is not self.model:
                continue
            columns = {getattr(c, "key", None) for c in getattr(rel, "local_columns", [])}
            if target == rel.key or target in columns:
                return str(rel.key)
        return None

    def _render_popup_form(
        self,
        request: Request,
        target: str,
        source: str | None = None,
        values: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        """Render the popup-form fragment used both for initial GET and error re-renders.

        ``source`` (the originating form's model slug) rides along on the POST
        URL so the created row is labelled per that form's ``relation_display``.
        """
        create_include = self.form_include
        if create_include and self.form_create_exclude:
            create_include = [f for f in create_include if f not in self.form_create_exclude]
        form = PydanticForm(
            self.model,
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
            norm = {k: [v] for k, v in errors.items()}
            form.errors = norm
            for fld in form.fields:
                fld.errors = norm.get(fld.name)
        post_url = admin_url_for(request, f"{self._model_name_lower}-create-popup")
        if source:
            post_url = post_url.include_query_params(source=source)
        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "form": form,
            "target": target,
            "values": values or {},
            "errors": errors or {},
            "post_url": post_url,
        }
        return self.templates.TemplateResponse(
            request,
            "widgets/popup_form.html",
            context,
            status_code=status_code,
        )
