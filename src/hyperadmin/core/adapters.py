from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import builtins

    from starlette.requests import Request

    from hyperadmin.core.choices import ChoiceItem
    from hyperadmin.core.inlines import InlineModelSpec

    QuerysetFilter = Callable[["Request | None"], dict[str, Any]]


@dataclass
class PaginationMeta:
    """Pagination metadata for list responses."""

    total: int
    page: int
    page_size: int


@dataclass
class ListEnvelope:
    """Response envelope for paginated list results.

    Structure: ``{data: [...], meta: {total, page, page_size}}``
    """

    data: builtins.list[dict[str, Any]]
    meta: PaginationMeta


class BaseAdapter(ABC):
    """Abstract base class for data adapters.

    Defines the contract for all data operations (get, list, create, update, delete).
    Subclass this to add support for a new ORM or data source.

    Example:
        ```python
        class MyAdapter(BaseAdapter):
            async def get(self, pk): ...
        ```
    """

    model: Any

    def __init__(self, model: Any, engine: Any) -> None:
        self.model = model
        self.engine = engine
        self._queryset_filter: QuerysetFilter | None = None

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        """Return additional equality filters merged into ``list()`` and ``get()`` queries.

        The returned mapping has the shape ``{column_name: value}`` and is applied as
        equality predicates **before** any view-layer filters. Use this hook to implement
        features like row-level security or tenant scoping without leaking those concerns
        into the view layer.

        Subclasses may override this method directly, or callers may register a
        per-request callable via :meth:`set_queryset_filter`. The callable is
        re-evaluated on every ``list()`` / ``get()`` — no caching — so it must be pure
        or request-scoped.

        Default behaviour returns an empty dict, which is a no-op (backward compatible).

        Args:
            request: The active Starlette/FastAPI request, when available. ``None`` is
                permitted so the hook is callable from contexts without an HTTP request
                (e.g. management scripts, tests).

        Returns:
            A dict of column-name to value pairs to be ANDed into the query's WHERE
            clause. Returns ``{}`` by default.
        """
        if self._queryset_filter is None:
            return {}
        return self._queryset_filter(request)

    def set_queryset_filter(self, filter_fn: QuerysetFilter) -> None:
        """Register a per-request callable that returns additional queryset filters.

        The callable receives the current :class:`starlette.requests.Request` (or
        ``None``) and must return a dict of ``{column_name: value}`` equality filters.
        It is re-invoked on every ``list()`` / ``get()`` so it may consult
        request-scoped state (e.g. ``request.state.user``).

        Args:
            filter_fn: A callable taking an optional :class:`Request` and returning a
                dict of equality filters.
        """
        self._queryset_filter = filter_fn

    def _resolve_queryset_filters(self, request: Request | None = None) -> dict[str, Any]:
        """Invoke :meth:`get_queryset` and validate the return type.

        Raises:
            TypeError: If ``get_queryset`` returns a value that is not a ``dict``.
        """
        result = self.get_queryset(request)
        if not isinstance(result, dict):
            raise TypeError(
                f"{type(self).__name__}.get_queryset() must return a dict, "
                f"got {type(result).__name__}"
            )
        return result

    @abstractmethod
    async def get(self, pk: Any) -> Any:
        """
        Retrieves a single object by its primary key.

        Args:
            pk: The primary key of the object to retrieve.

        Returns:
            The retrieved object, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        search_fields: builtins.list[str] | None = None,
    ) -> tuple[builtins.list[Any], int]:
        """
        Retrieves a list of objects with optional pagination, searching, and filtering.

        Args:
            page: The page number for pagination.
            page_size: The number of items per page.
            search: A search query to filter the results.
            filters: A dictionary of filters to apply to the query.
            order_by: The field to order the results by.

        Returns:
            A tuple containing the list of objects and the total count of objects.
        """
        raise NotImplementedError

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> Any:
        """
        Creates a new object.

        Args:
            data: A dictionary of data for the new object.

        Returns:
            The created object.
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        """
        Updates an existing object.

        Args:
            pk: The primary key of the object to update.
            data: A dictionary of data to update the object with.

        Returns:
            The updated object.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, pk: Any) -> None:
        """
        Deletes an object by its primary key.

        Args:
            pk: The primary key of the object to delete.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        """
        Retrieves related objects for a given object and field.

        Args:
            pk: The primary key of the object.
            field: The name of the relationship field.

        Returns:
            A list of related objects.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]:
        """
        Retrieves the schema definition for the model.

        Returns:
            A dictionary representing the model's schema.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        """Return paginated, searchable choices for a relation field.

        Args:
            field: The relation field name on this adapter's model.
            q: Optional search string (ILIKE match on string columns).
            limit: Max results to return. Must not exceed 200.
            offset: Number of rows to skip for pagination.
            **filters: Extra equality filters forwarded to the query (cascading support).

        Returns:
            A list of ``ChoiceItem`` dicts with ``value``, ``label``, ``selected=False``.

        Raises:
            ValueError: When ``limit`` exceeds 200.
        """
        raise NotImplementedError

    @abstractmethod
    async def save_inline_rows(
        self,
        spec: InlineModelSpec,
        rows: builtins.list[dict[str, Any]],
        parent_pk: Any,
    ) -> None:
        """Persist validated inline rows — create, update, or delete as needed.

        Args:
            spec: The ``InlineModelSpec`` describing the related model and FK field.
            rows: Validated row dicts, each optionally containing ``_pk`` (for
                update/delete) and ``_delete`` (for deletion).
            parent_pk: The primary key of the parent object to associate new rows with.
        """
        raise NotImplementedError


class JsonApiAdapter(BaseAdapter, ABC):
    """Adapter that adds JSON:API-style serialisation to BaseAdapter.

    Subclasses must implement all ``BaseAdapter`` abstract methods **and**
    ``to_dict``, which converts a single ORM/domain record into a plain
    dictionary suitable for inclusion in a ``ListEnvelope``.

    Example:
        ```python
        class MySqlModelJsonAdapter(JsonApiAdapter):
            def to_dict(self, record):
                return record.model_dump()
        ```
    """

    @abstractmethod
    def to_dict(self, record: Any) -> dict[str, Any]:
        """Serialise a single record to a plain dictionary.

        Args:
            record: A domain object or ORM model instance.

        Returns:
            A JSON-serialisable dictionary representation of the record.
        """
        raise NotImplementedError

    async def list_as_envelope(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
    ) -> ListEnvelope:
        """Return a paginated list wrapped in a ``ListEnvelope``.

        Delegates to ``self.list()`` for data retrieval, then serialises each
        record via ``self.to_dict()``.

        Args:
            page: The page number for pagination.
            page_size: The number of items per page.
            search: A search query to filter the results.
            filters: A dictionary of filters to apply to the query.
            order_by: The field to order the results by.

        Returns:
            A ``ListEnvelope`` containing serialised records and pagination metadata.
        """
        records, total = await self.list(
            page=page,
            page_size=page_size,
            search=search,
            filters=filters,
            order_by=order_by,
        )
        return ListEnvelope(
            data=[self.to_dict(record) for record in records],
            meta=PaginationMeta(total=total, page=page, page_size=page_size),
        )
