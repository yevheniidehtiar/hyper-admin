"""JSON API router that auto-generates 5 CRUD endpoints per registered model.

Endpoints generated for each model:
- ``GET    /api/{model}``         — paginated list
- ``GET    /api/{model}/{id}``    — detail
- ``POST   /api/{model}``         — create
- ``PUT    /api/{model}/{id}``    — update
- ``DELETE /api/{model}/{id}``    — delete
"""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    page: int
    page_size: int
    total: int
    total_pages: int


class ListEnvelope(BaseModel):
    """Standard envelope for paginated list responses."""

    data: list[dict[str, Any]]
    pagination: PaginationMeta


class DetailEnvelope(BaseModel):
    """Standard envelope for single-item responses."""

    data: dict[str, Any]


class DeletedEnvelope(BaseModel):
    """Standard envelope for delete confirmation responses."""

    deleted: bool
    id: Any


def _serialize(obj: Any) -> dict[str, Any]:
    """Convert a model instance to a JSON-safe dictionary."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()  # type: ignore[union-attr]
    return dict(obj)  # pragma: no cover


# ---------------------------------------------------------------------------
# Factory functions — each returns an async handler with the adapter captured
# in a proper closure so FastAPI never sees it as a dependency parameter.
# ---------------------------------------------------------------------------


def _make_list_view(adapter: BaseAdapter) -> Callable[..., Awaitable[ListEnvelope]]:
    async def list_view(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
        search: str | None = Query(None),
    ) -> ListEnvelope:
        items, total = await adapter.list(
            page=page,
            page_size=page_size,
            search=search or None,
        )
        total_pages = max(1, math.ceil(total / page_size))
        return ListEnvelope(
            data=[_serialize(item) for item in items],
            pagination=PaginationMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
            ),
        )

    return list_view


def _make_detail_view(adapter: BaseAdapter) -> Callable[..., Awaitable[DetailEnvelope]]:
    async def detail_view(item_id: int) -> DetailEnvelope:
        obj = await adapter.get(item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        return DetailEnvelope(data=_serialize(obj))

    return detail_view


def _make_create_view(adapter: BaseAdapter) -> Callable[..., Awaitable[DetailEnvelope]]:
    async def create_view(request: Request) -> DetailEnvelope:
        body = await request.json()
        obj = await adapter.create(body)
        return DetailEnvelope(data=_serialize(obj))

    return create_view


def _make_update_view(adapter: BaseAdapter) -> Callable[..., Awaitable[DetailEnvelope]]:
    async def update_view(item_id: int, request: Request) -> DetailEnvelope:
        body = await request.json()
        obj = await adapter.update(item_id, body)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        return DetailEnvelope(data=_serialize(obj))

    return update_view


def _make_delete_view(adapter: BaseAdapter) -> Callable[..., Awaitable[DeletedEnvelope]]:
    async def delete_view(item_id: int) -> DeletedEnvelope:
        obj = await adapter.get(item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Not found")
        await adapter.delete(item_id)
        return DeletedEnvelope(deleted=True, id=item_id)

    return delete_view


# ---------------------------------------------------------------------------
# Route builder
# ---------------------------------------------------------------------------


def _build_crud_routes(
    router: APIRouter,
    model_name: str,
    adapter: BaseAdapter,
    options: AdminOptions,
) -> None:
    """Register CRUD endpoint handlers on *router* for a single model."""
    prefix = f"/{model_name}"

    if options.can_list:
        router.add_api_route(
            prefix,
            _make_list_view(adapter),
            methods=["GET"],
            name=f"api-{model_name}-list",
            response_model=ListEnvelope,
        )

    if options.can_detail:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            _make_detail_view(adapter),
            methods=["GET"],
            name=f"api-{model_name}-detail",
            response_model=DetailEnvelope,
        )

    if options.can_create:
        router.add_api_route(
            prefix,
            _make_create_view(adapter),
            methods=["POST"],
            name=f"api-{model_name}-create",
            response_model=DetailEnvelope,
        )

    if options.can_edit:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            _make_update_view(adapter),
            methods=["PUT"],
            name=f"api-{model_name}-update",
            response_model=DetailEnvelope,
        )

    if options.can_delete:
        router.add_api_route(
            f"{prefix}/{{item_id:int}}",
            _make_delete_view(adapter),
            methods=["DELETE"],
            name=f"api-{model_name}-delete",
            response_model=DeletedEnvelope,
        )


class JsonApiRouter:
    """Generates a FastAPI ``APIRouter`` with JSON CRUD endpoints for every registered model.

    Usage::

        json_router = JsonApiRouter(engine=engine)
        json_router.generate_routes()
        app.include_router(json_router.router, prefix="/api")

    Each registered model gets five endpoints (subject to ``AdminOptions``):

    - ``GET    /{model}``          — paginated list
    - ``GET    /{model}/{id}``     — single item detail
    - ``POST   /{model}``          — create
    - ``PUT    /{model}/{id}``     — update
    - ``DELETE /{model}/{id}``     — delete
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.router = APIRouter()

    def generate_routes(self) -> None:
        """Iterate the site registry and build CRUD routes for each model."""
        self.router = APIRouter()

        for model, admin_class in site._registry.items():
            admin_instance = admin_class(model)
            options: AdminOptions = getattr(admin_class, "options", None) or AdminOptions()
            adapter = admin_instance.adapter_class(model, engine=self.engine)
            model_name = model.__name__.lower()

            _build_crud_routes(
                router=self.router,
                model_name=model_name,
                adapter=adapter,
                options=options,
            )

    def get_router(self) -> APIRouter:
        """Return the assembled ``APIRouter``."""
        return self.router
