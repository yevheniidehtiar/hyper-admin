"""Record search for the command palette (st-v059-nav-05).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Addendum: record search). One
model's part of ``GET {prefix}/nav/search``: the endpoint in
``views/palette_search.py`` asks each opted-in model's view for its matches.
"""

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from hyperadmin.core.display import get_display_name
from hyperadmin.views.dynamic.base import DynamicModelViewBase
from hyperadmin.views.dynamic.helpers import _request_scoped
from hyperadmin.views.urls import admin_url_for

logger = logging.getLogger(__name__)


class PaletteSearchMixin(DynamicModelViewBase):
    """``palette_records``: this model's records for the palette."""

    async def _palette_route(self, request: Request) -> str | None:
        """The route a found record opens for this user: edit, else detail, else none.

        The same rule as a list row (``ListViewMixin._row_access``) without the
        delete check, which the palette does not need.
        """
        model = self._model_name_lower
        if self.options.can_edit and await self._has_permission(request, f"change_{model}"):
            return f"{model}-update-form"
        if self.options.can_detail:
            return f"{model}-detail"
        return None

    @_request_scoped
    async def palette_records(
        self, request: Request, query: str, limit: int
    ) -> list[dict[str, str]] | None:
        """Up to ``limit`` records matching ``query``, or ``None`` when nothing was queried.

        ``None`` means the model was skipped without touching its table: it has
        no search fields, the user lacks ``view_<model>``, or a found record
        would have no page to open. The search is the list view's own
        (``search_fields``, ``get_queryset`` scoping, default sort). A database
        error is logged and returns no records, so one broken table never
        breaks the palette.
        """
        if not self.search_fields:
            return None
        if not await self._has_permission(request, f"view_{self._model_name_lower}"):
            return None
        route = await self._palette_route(request)
        if route is None:
            return None
        try:
            items, _total = await self.adapter.list(
                page=1,
                page_size=limit,
                search=query,
                order_by=self._default_sort_field(),
                search_fields=self.search_fields,
            )
        except SQLAlchemyError:
            logger.exception("Palette search on %s failed", self.model.__name__)
            return []
        return [self._palette_record(request, route, item) for item in items]

    def _palette_record(self, request: Request, route: str, item: Any) -> dict[str, str]:
        """One result: the record's display name and the path of the page it opens."""
        item_id = self.pk.to_str(self.pk.value_of(item))
        return {
            "label": get_display_name(item, pk_attr=self.pk.attr),
            "url": admin_url_for(request, route, item_id=item_id).path,
        }
