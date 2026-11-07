"""``GET {prefix}/nav/search``: record search for the command palette (st-v059-nav-05).

Spec: ``docs/specs/navigation-and-list-ux.md`` (Addendum: record search).
``HyperAdminRouter`` adds one :class:`PaletteSearch` source per model with
``AdminOptions.palette_search`` and registers the route only when there is at
least one. Each request asks the sources in registry order and stops after
:data:`MODELS_PER_REQUEST` models were queried; each model returns at most
:data:`RESULTS_PER_MODEL` records. Permission and ``get_queryset`` scoping are
the model view's (``views/dynamic/palette_search.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Query, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from fastapi import APIRouter

__all__ = [
    "MAX_QUERY_LENGTH",
    "MIN_QUERY_LENGTH",
    "MODELS_PER_REQUEST",
    "RESULTS_PER_MODEL",
    "PaletteSearch",
    "PaletteSource",
]

#: Shorter queries return no records and touch no table.
MIN_QUERY_LENGTH = 2
#: Longer queries are refused with 422.
MAX_QUERY_LENGTH = 100
#: Records returned per model.
RESULTS_PER_MODEL = 5
#: Models queried per request; later opted-in models are skipped.
MODELS_PER_REQUEST = 6


@dataclass(frozen=True)
class PaletteSource:
    """One opted-in model: its nav key, plural label and view."""

    key: str
    label: Any
    view: Any


class PaletteSearch:
    """The palette's record search over the opted-in models of one admin."""

    def __init__(self) -> None:
        self.sources: list[PaletteSource] = []

    @property
    def keys(self) -> frozenset[str]:
        """Nav keys of the opted-in models."""
        return frozenset(source.key for source in self.sources)

    def add(self, source: PaletteSource) -> None:
        """Offer ``source`` 's records in the palette."""
        self.sources.append(source)

    def register(self, router: APIRouter) -> None:
        """Add ``GET /nav/search`` to ``router``."""
        router.add_api_route(
            "/nav/search",
            self.search,
            methods=["GET"],
            name="admin-palette-search",
            include_in_schema=False,
        )

    async def search(
        self, request: Request, q: Annotated[str, Query(max_length=MAX_QUERY_LENGTH)] = ""
    ) -> JSONResponse:
        """Records matching ``q``, grouped by model: ``{"groups": [{key, label, items}]}``.

        Each item is ``{"label", "url"}``. Models with no match are left out.
        The response is never cached: it depends on the user.
        """
        query = q.strip()
        groups: list[dict[str, Any]] = []
        queried = 0
        if len(query) >= MIN_QUERY_LENGTH:
            for source in self.sources:
                if queried == MODELS_PER_REQUEST:
                    break
                records = await source.view.palette_records(request, query, RESULTS_PER_MODEL)
                if records is None:
                    continue
                queried += 1
                if records:
                    groups.append(
                        {
                            "key": source.key,
                            "label": str(source.label),
                            "items": records,
                        }
                    )
        return JSONResponse({"groups": groups}, headers={"Cache-Control": "no-store"})
