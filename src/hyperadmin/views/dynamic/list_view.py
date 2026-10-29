"""The list view: filters, query, HTMX body swap and pagination."""

import logging
import math
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlencode

from fastapi import Query, Request
from markupsafe import Markup
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import QueryParams
from starlette.responses import RedirectResponse

from hyperadmin.core.choices import ChoiceItem
from hyperadmin.core.discovery import build_filter_metadata
from hyperadmin.core.display import get_display_name, preview_structured
from hyperadmin.core.filtering import (
    FilterCondition,
    ParsedFilters,
    parse_filter_params,
)
from hyperadmin.core.filters_compat import LegacyFieldFilter, collect_filters
from hyperadmin.core.schema import schema_for
from hyperadmin.filters.base import FilterBinding, FilterDef, FilterRenderContext, clear_href
from hyperadmin.filters.choice import MultiChoiceFilter
from hyperadmin.filters.date import CurrentPeriodDefault
from hyperadmin.filters.relation import MultiFKFilter
from hyperadmin.views.dynamic.helpers import (
    _LIST_FILTER_OPS,
    _MAX_LIST_PAGE,
    LIST_BODY_ID,
    _is_missing_table_error,
    _ListFilters,
    _request_scoped,
)
from hyperadmin.views.dynamic.saved_views import SavedViewsMixin
from hyperadmin.views.template_filters import TIMEZONE_GLOBAL, request_tz

logger = logging.getLogger(__name__)


class ListViewMixin(SavedViewsMixin):
    """The list view: filters, query, HTMX body swap and pagination."""

    def _parse_list_filters(self, request: Request) -> ParsedFilters:
        """Parse ``filter_<field>`` query params into typed conditions (BYOA SDD D.3).

        Only whitelisted (``list_filter``), non-sensitive model fields are
        honoured; anything else is ignored so the URL cannot become an equality
        oracle on arbitrary columns. Only the ``exact`` operator is accepted
        (Owner decision 8 defers ranges). A value that does not fit the field's
        type (``filter_age=abc``) drops its condition and is reported in
        ``errors`` instead, so user input never reaches the database as a query
        that fails. Dates on aware columns are local days in the display timezone.
        """
        return parse_filter_params(
            self.model,
            request.query_params,
            self._filterable_fields(),
            tz=request_tz(request, self.templates.env.globals.get(TIMEZONE_GLOBAL)),
            datetime_kind=self.adapter.datetime_kind,
            ops=_LIST_FILTER_OPS,
        )

    def _filter_defs(self) -> list[FilterDef]:
        """``options.list_filter`` as filter definitions, in order, sensitive fields dropped.

        Strings become :class:`LegacyFieldFilter` (only when they name a
        filterable field); explicit definitions are kept unless they bind to a
        sensitive column, which can never be filtered on.
        """
        allowed = self._filterable_fields()
        defs: list[FilterDef] = []
        for filter_def in collect_filters(self.options.list_filter):
            if isinstance(filter_def, LegacyFieldFilter):
                if filter_def.field in allowed:
                    defs.append(filter_def)
            elif filter_def.field not in self._sensitive_fields:
                defs.append(filter_def)
        return defs

    def _explicit_filters(self) -> list[FilterDef]:
        """The non-legacy filter definitions: the ones that compile through ``FilterDef``."""
        return [f for f in self._filter_defs() if not isinstance(f, LegacyFieldFilter)]

    def _filter_binding(self, request: Request) -> FilterBinding:
        """Per-request facts the filters compile against (timezone, user key, model)."""
        return FilterBinding(
            model=self.model,
            tz=request_tz(request, self.templates.env.globals.get(TIMEZONE_GLOBAL)),
            datetime_kind=self.adapter.datetime_kind,
            user=getattr(request.state, "user", None),
            user_key=getattr(request.state, "user_key", None),
        )

    @staticmethod
    def _compile_explicit(
        explicit: list[FilterDef], query: Any, binding: FilterBinding
    ) -> list[FilterCondition]:
        """Every explicit filter's typed conditions for ``query``, in ``list_filter`` order."""
        conditions: list[FilterCondition] = []
        for filter_def in explicit:
            conditions.extend(filter_def.compile(filter_def.parse(query), binding))
        return conditions

    @staticmethod
    def _period_default_query(
        explicit: list[FilterDef], query: QueryParams, binding: FilterBinding
    ) -> str | None:
        """``query`` with every applicable ``CurrentPeriodDefault`` made explicit, or ``None``.

        The querystring is the single source of truth (SDD decision): on first
        load the default's ``{field}__gte``/``__lte`` pair is pushed into the
        URL rather than applied silently. ``None`` means no default applies
        (the user already chose dates, or asked for ``{field}=all``).
        """
        current = query
        changed = False
        for filter_def in explicit:
            if not isinstance(filter_def, CurrentPeriodDefault):
                continue
            pushed = filter_def.redirect_query(current, binding)
            if pushed is not None:
                current = QueryParams(pushed)
                changed = True
        return str(current) if changed else None

    def _wants_list_body(self, request: Request, explicit: list[FilterDef]) -> bool:
        """Whether an HTMX request gets the ``<tbody>`` fragment instead of the table.

        htmx names its target in ``HX-Target``: the filter sidebar targets the
        body (:data:`LIST_BODY_ID`), while search, sort and pagination target
        the whole table. A target-less HTMX request (a scripted client) gets
        the body when the model uses the filter library, and the full table
        otherwise (the pre-0.5.6 contract).
        """
        target = request.headers.get("hx-target")
        if target == LIST_BODY_ID:
            return True
        if target:
            return False
        return bool(explicit)

    @staticmethod
    def _needs_choices(filter_def: FilterDef) -> bool:
        """Whether the sidebar needs prefetched options to render ``filter_def``."""
        if isinstance(filter_def, MultiFKFilter):
            return True
        return isinstance(filter_def, MultiChoiceFilter) and filter_def.choices is None

    async def _choices_by_field(
        self, request: Request, explicit: list[FilterDef]
    ) -> dict[str, Sequence[ChoiceItem]]:
        """Prefetched options keyed by field, for the explicit filters that list rows or values."""
        model_fields = schema_for(self.model).model_fields
        fields: list[str] = []
        for filter_def in explicit:
            name = filter_def.field
            if (
                self._needs_choices(filter_def)
                and name in model_fields
                and name not in fields
                and await self._may_view_related(request, self._relation_target_for_field(name))
            ):
                fields.append(name)
        if not fields:
            return {}
        metadata = await build_filter_metadata(
            self.model, fields, self.adapter, self._applied_filter_values(request, fields)
        )
        return {entry["name"]: entry["choices"] for entry in metadata}

    async def _filter_groups(
        self, request: Request, binding: FilterBinding
    ) -> list[dict[str, Any]]:
        """One rendered sidebar group per filter definition, legacy strings included.

        Each entry carries the definition, its rendered HTML (``html``), whether
        it is active, the chip text for the applied-filters strip, the inline
        error for invalid input and the href that clears it.
        """
        defs = self._filter_defs()
        if not defs:
            return []
        query = request.query_params
        choices = await self._choices_by_field(
            request, [f for f in defs if not isinstance(f, LegacyFieldFilter)]
        )
        for entry in await self._get_filter_metadata(request):
            choices.setdefault(entry["name"], entry["choices"])
        groups: list[dict[str, Any]] = []
        for filter_def in defs:
            parsed = filter_def.parse(query)
            ctx = FilterRenderContext(
                query=query,
                binding=binding,
                choices=choices.get(filter_def.field, ()),
                templates=self.templates.env,
            )
            groups.append(
                {
                    "filter": filter_def,
                    "slug": filter_def.slug,
                    "title": filter_def.title,
                    # Rendered by the admin's own autoescaping Jinja environment.
                    "html": Markup(filter_def.render(ctx)),  # noqa: S704
                    "active": bool(parsed),
                    "chip": filter_def.describe(parsed),
                    "error": filter_def.error(query),
                    "clear_href": clear_href(query, filter_def.query_keys),
                }
            )
        return groups

    @staticmethod
    def _explicit_query(explicit: list[FilterDef], query: QueryParams) -> str:
        """The explicit filters' raw pairs as ``&k=v...`` for links that must keep them.

        Pagination and sort links append it next to the legacy ``filter_*``
        pairs, so a date range or "Mine only" survives a page change.
        """
        keys = {key for filter_def in explicit for key in filter_def.query_keys}
        if not keys:
            return ""
        pairs = [(k, v) for k, v in query.multi_items() if k in keys]
        return f"&{urlencode(pairs)}" if pairs else ""

    def _list_filters(self, request: Request) -> _ListFilters:
        """Run both filter pipelines over the querystring (see :meth:`list_view`)."""
        parsed = self._parse_list_filters(request)
        explicit = self._explicit_filters()
        conditions = list(parsed.conditions)
        if not explicit:
            return _ListFilters(parsed, explicit, None, conditions, None)
        binding = self._filter_binding(request)
        query = request.query_params
        conditions.extend(self._compile_explicit(explicit, query, binding))
        pushed = self._period_default_query(explicit, query, binding)
        return _ListFilters(parsed, explicit, binding, conditions, pushed)

    def _list_rows(
        self, items: list[Any], file_fields: set[str], request: Request | None = None
    ) -> list[dict[str, Any]]:
        """``column_list`` cells per item, plus ``_pk`` (and ``id`` for custom templates).

        With a ``request``, each row also carries ``_thumbs``: the 40x40 thumbnail
        URL of every image column that has a stored file.
        """
        image_fields = set(self.column_list) & self._get_image_fields() if request else set()
        rows: list[dict[str, Any]] = []
        for item in items:
            row: dict[str, Any] = {}
            for field in self.column_list:
                if field == "__str__":
                    row[field] = get_display_name(item)
                else:
                    val = getattr(item, field, None)
                    if field in file_fields and val is not None:
                        val = val.name if hasattr(val, "name") else str(val)
                    elif isinstance(val, BaseModel):
                        # A related row: never its default __str__ (prints secrets).
                        val = get_display_name(val)
                    row[field] = preview_structured(val)
            row["_pk"] = self.pk.value_of(item)
            if request is not None:
                row["_thumbs"] = self._thumbnail_urls(
                    request, row["_pk"], row, "list", image_fields
                )
            # Custom templates still read ``item.id`` on int-id models.
            if hasattr(item, "id"):
                row["id"] = item.id
            rows.append(row)
        return rows

    def _list_template(self, request: Request, filters: _ListFilters) -> tuple[str, dict[str, str]]:
        """The template and extra headers for a list response.

        HTMX gets the table for search/sort/pagination and the body alone for
        the filter sidebar (plus ``HX-Push-Url`` so the URL carries the filter
        state); everything else gets the full layout.
        """
        if not request.headers.get("hx-request"):
            return self._get_template_name("list"), {}
        if not self._wants_list_body(request, filters.explicit):
            return "components/table.html", {}
        pushed = filters.pushed_query
        if pushed is None:
            pushed = str(request.query_params)
        path = self._list_path(request)
        return "components/table_body.html", {"HX-Push-Url": f"{path}?{pushed}" if pushed else path}

    @_request_scoped
    async def list_view(
        self,
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        search: str = Query(""),
        sort_by: str = Query(None),
        sort_direction: str = Query("asc", pattern="^(asc|desc)$"),
    ):
        """Renders the list view for the model with pagination, sorting, and filtering.

        Filtering runs two pipelines over one whitelist: legacy ``list_filter``
        strings keep the typed ``filter_<field>`` contract (with ``filter_errors``),
        and explicit :class:`FilterDef` entries parse their own keys and compile
        through ``FilterDef.compile`` (filter library SDD). An HTMX request from
        the filter sidebar gets only the ``<tbody>`` plus ``HX-Push-Url``, so
        the URL stays the source of truth; ``?view=<id>`` loads a saved view.
        """
        await self._check_permission(request, "view")
        query = request.query_params
        is_htmx = bool(request.headers.get("hx-request"))

        view_ref = query.get("view")
        if view_ref is not None and self._saved_views_available(request):
            return RedirectResponse(
                url=await self._resolve_saved_view(request, view_ref), status_code=302
            )

        filters = self._list_filters(request)
        parsed_filters = filters.parsed
        if filters.pushed_query is not None and not is_htmx:
            # First load with a CurrentPeriodDefault: make the default
            # explicit in the URL before rendering anything.
            target = f"{self._list_path(request)}?{filters.pushed_query}"
            return RedirectResponse(url=target, status_code=302, headers={"HX-Push-Url": target})

        # sort_by is whitelisted against the sortable displayed columns. An
        # unknown or sensitive value falls back to the default sort.
        if sort_by and sort_by not in self._sortable_fields():
            logger.debug("Ignoring sort on non-sortable field %r", sort_by)
            sort_by = ""
            sort_direction = "asc"
        if not sort_by:
            sort_by = self._default_sort_field()

        # Format order_by for adapter (use negative prefix for descending)
        order_by = f"-{sort_by}" if sort_direction == "desc" else sort_by
        page = min(page, _MAX_LIST_PAGE)
        list_error: dict[str, bool] | None = None

        try:
            # The handler runs inside the request's queryset scope, so
            # ModelAdmin.get_queryset(request) is merged into the WHERE clause.
            items, total_items = await self.adapter.list(
                page=page,
                page_size=page_size,
                search=search or None,
                filters=filters.conditions,
                order_by=order_by,
                search_fields=self.search_fields,
            )

            # Calculate pagination info
            total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
            start_index = (page - 1) * page_size + 1 if total_items > 0 else 0
            end_index = min(page * page_size, total_items)

            pagination = {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
                "start_index": start_index,
                "end_index": end_index,
            }

        except SQLAlchemyError as exc:
            # Only database errors are handled here; user input is validated
            # above, and any other exception is a bug that must propagate.
            logger.exception("Listing %s failed", self.model.__name__)
            if self.debug:
                raise
            list_error = {"missing_table": _is_missing_table_error(exc)}
            items = []
            pagination = {
                "page": 1,
                "page_size": page_size,
                "total_items": 0,
                "total_pages": 0,
                "start_index": 0,
                "end_index": 0,
            }

        file_fields = self._get_file_fields()
        rows = self._list_rows(items, file_fields, request)

        # Get filter metadata if list_filter is configured. Skipped when the
        # list query failed: relation filters query the database again, and a
        # second failure would turn the list-error banner into a bare 500.
        show_filters = bool(self.options.list_filter) and list_error is None
        filter_metadata = await self._get_filter_metadata(request) if show_filters else []
        # The sidebar groups (every filter, rendered) and the applied chips;
        # legacy-only models render the groups too, so a sidebar can show them.
        filter_groups = (
            await self._filter_groups(request, filters.binding or self._filter_binding(request))
            if show_filters
            else []
        )
        applied_filters = [
            {
                "slug": group["slug"],
                "label": group["title"],
                "value": group["chip"],
                "clear_href": group["clear_href"],
            }
            for group in filter_groups
            if group["chip"]
        ]

        context = {
            "request": request,
            "pk_attr": self.pk.attr,
            "model_name": self.model.__name__,
            "fields": self.column_list,
            "field_labels": self.field_labels,
            "items": rows,
            "pagination": pagination,
            "search_query": search,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
            "filter_metadata": filter_metadata,
            "active_filters": parsed_filters.active,
            "filter_errors": parsed_filters.errors,
            "filter_groups": filter_groups,
            "applied_filters": applied_filters,
            "filter_query": self._explicit_query(filters.explicit, query),
            "list_body_id": LIST_BODY_ID,
            **await self._saved_views_context(request, loaded=list_error is None),
            "can_create": self.options.can_create,
            "can_edit": self.options.can_edit,
            "can_delete": self.options.can_delete,
            "can_detail": self.options.can_detail,
            "file_fields": file_fields,
            "options": self.options,
            "list_editable": list(self.options.list_editable or []),
            "list_error": list_error,
            "bulk_actions": [a for a in self.actions if a.bulk],
        }

        template_name, headers = self._list_template(request, filters)
        # A failed full page is a 500; an HTMX partial stays 200 so htmx swaps
        # the banner in instead of discarding the response.
        status_code = 500 if list_error is not None and not is_htmx else 200
        return self.templates.TemplateResponse(
            request, template_name, context, status_code=status_code, headers=headers
        )
