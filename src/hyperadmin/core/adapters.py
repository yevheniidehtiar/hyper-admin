from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

from hyperadmin.core.primary_key import DEFAULT_PK, InvalidPrimaryKey, PrimaryKeyInfo
from hyperadmin.core.schema import schema_for
from hyperadmin.core.timezones import annotation_datetime_kind

if TYPE_CHECKING:
    import builtins

    from starlette.requests import Request

    from hyperadmin.core.cache import CountCache
    from hyperadmin.core.choices import ChoiceItem
    from hyperadmin.core.filtering import FilterCondition
    from hyperadmin.core.inlines import InlineModelSpec
    from hyperadmin.core.timezones import DateTimeKind

    QuerysetFilter = Callable[["Request | None"], dict[str, Any]]


logger = logging.getLogger(__name__)


class AsyncSessionLike(Protocol):
    """Structural shape of the session object a ``session_factory`` yields.

    Lists only the methods HyperAdmin's adapters and auth services actually
    call. A ``Protocol`` describes the shape without importing a concrete ORM
    session class, so ``core/`` stays free of ORM code while ``SessionFactory``
    still type-checks what a session must support.
    """

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any: ...
    async def get(self, entity: Any, ident: Any) -> Any: ...
    def add(self, instance: Any) -> None: ...
    def add_all(self, instances: Any) -> None: ...
    async def commit(self) -> None: ...
    async def refresh(self, instance: Any, *args: Any, **kwargs: Any) -> None: ...
    async def delete(self, instance: Any) -> None: ...


#: A zero-argument callable returning an async context manager that yields a
#: session (``async_sessionmaker(engine)`` already satisfies this). Typing only
#: — ``core/`` never imports an ORM session class to define it.
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSessionLike]]

#: Resolves the row-scoping callable for a model class inside a request scope.
QuerysetFilterResolver = Callable[[Any], "Callable[[Any], dict[str, Any]] | None"]


def require_engine_or_session_factory(cls_name: str, engine: Any, session_factory: Any) -> None:
    """Raise ``ValueError`` unless at least one of ``engine`` / ``session_factory`` is set.

    Shared by every class that accepts this seam (``BaseAdapter``,
    ``SessionAuthBackend``, ``PermissionSyncService``, ``ModelPermissionChecker``)
    so the condition and message can never drift between them.
    """
    if engine is None and session_factory is None:
        msg = (
            f"{cls_name} requires either engine= (an async SQLAlchemy engine) or "
            "session_factory= (e.g. async_sessionmaker(engine))."
        )
        raise ValueError(msg)


def open_session(
    engine: Any, session_factory: SessionFactory | None
) -> AbstractAsyncContextManager[AsyncSessionLike]:
    """Open a session from whichever of ``engine`` / ``session_factory`` was given.

    Prefers ``session_factory`` (the host's own session maker) when set, so a
    host-managed engine, connection pool and transaction scope are respected.
    Falls back to opening a plain ``AsyncSession`` on ``engine`` for the
    legacy, engine-only construction path. Shared by ``BaseAdapter._session``
    and the auth services' ``_session`` methods.
    """
    if session_factory is not None:
        return session_factory()
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415

    # AsyncSession satisfies AsyncSessionLike structurally; mypy's generic
    # AbstractAsyncContextManager check needs the hint spelled out explicitly.
    return cast("AbstractAsyncContextManager[AsyncSessionLike]", AsyncSession(engine))


class InlineRowNotOwnedError(LookupError):
    """A submitted inline child pk is not an existing child of the parent being saved.

    Raised before any write so the view can answer 404 (IDOR / reparenting guard).
    """


#: Sentinel marking a submitted inline ``_pk`` that failed to parse against the
#: child model's primary-key codec — see ``BaseAdapter.ensure_inline_rows_owned``.
_FOREIGN = object()


@dataclass(frozen=True)
class QuerysetScope:
    """The request-scoped row filter active for the current task.

    Attributes:
        request: The active request, passed to each model's queryset callable.
        resolver: Maps a model class to its queryset callable (typically the
            registered ``ModelAdmin.get_queryset``) or ``None`` when the model
            has no row scoping.
    """

    request: Any
    resolver: QuerysetFilterResolver

    def filters_for(self, model: Any, request: Any = None) -> dict[str, Any]:
        """Evaluate the queryset callable for ``model`` (``{}`` when there is none)."""
        filter_fn = self.resolver(model)
        if filter_fn is None:
            return {}
        result = filter_fn(request if request is not None else self.request)
        if not isinstance(result, dict):
            raise TypeError(
                f"get_queryset() for {getattr(model, '__name__', model)!s} must return a dict, "
                f"got {type(result).__name__}"
            )
        return result


_QUERYSET_SCOPE: ContextVar[QuerysetScope | None] = ContextVar(
    "hyperadmin_queryset_scope", default=None
)


@contextmanager
def queryset_scope(request: Any, resolver: QuerysetFilterResolver) -> Iterator[QuerysetScope]:
    """Activate row scoping for the current request.

    The scope lives in a :class:`contextvars.ContextVar`, not on the (shared,
    long-lived) adapter instance, so concurrent requests can never observe each
    other's filters. Nested scopes restore the outer scope on exit.
    """
    scope = QuerysetScope(request=request, resolver=resolver)
    token = _QUERYSET_SCOPE.set(scope)
    try:
        yield scope
    finally:
        _QUERYSET_SCOPE.reset(token)


def current_queryset_scope() -> QuerysetScope | None:
    """Return the active :class:`QuerysetScope`, or ``None`` outside a request scope."""
    return _QUERYSET_SCOPE.get()


def scoped_queryset_filters(model: Any, request: Any = None) -> dict[str, Any]:
    """Return the request-scoped equality filters for ``model`` (``{}`` outside a scope)."""
    scope = _QUERYSET_SCOPE.get()
    if scope is None:
        return {}
    return scope.filters_for(model, request)


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
    #: Primary-key codec for ``model``. ORM adapters replace it with an introspected
    #: value; third-party adapters inherit the historical ``int id`` default.
    pk: PrimaryKeyInfo = DEFAULT_PK
    #: Where list totals are cached, and for how long. Set by the router from
    #: ``AdminOptions.count_cache_ttl``; ``0`` (the default) disables caching.
    count_cache: CountCache | None = None
    count_cache_ttl: int = 0

    def __init__(
        self, model: Any, engine: Any = None, *, session_factory: SessionFactory | None = None
    ) -> None:
        require_engine_or_session_factory(type(self).__name__, engine, session_factory)
        self.model = model
        self.engine = engine
        self.session_factory = session_factory
        self._queryset_filter: QuerysetFilter | None = None

    def _session(self) -> AbstractAsyncContextManager[AsyncSessionLike]:
        """Open a session from whichever of ``engine`` / ``session_factory`` was given.

        Prefers ``session_factory`` (the host's own session maker) when set, so a
        host-managed engine, connection pool and transaction scope are respected.
        Falls back to opening a plain ``AsyncSession`` on ``engine`` for the legacy,
        engine-only construction path.
        """
        return open_session(self.engine, self.session_factory)

    async def _cached_count(
        self,
        compute: Callable[[], Awaitable[int]],
        *,
        filters: Sequence[FilterCondition],
        search: str | None,
        search_fields: Sequence[str] | None,
        queryset_filters: Mapping[str, Any],
    ) -> int:
        """Return the list total, served from :attr:`count_cache` while fresh.

        ``page``, ``page_size`` and ordering do not change a total, so they are not
        part of the key. A query whose values cannot be hashed bypasses the cache.
        """
        cache = self.count_cache
        if cache is None or self.count_cache_ttl <= 0:
            return await compute()
        key = (
            self._count_cache_model_key(),
            tuple(filters),
            search or "",
            tuple(search_fields) if search and search_fields is not None else None,
            tuple(sorted(queryset_filters.items())),
        )
        try:
            hash(key)
        except TypeError:
            logger.debug("count cache bypassed for %s: unhashable filter value", key[0])
            return await compute()
        cached = await cache.get(key)
        if cached is not None:
            return cached
        total = await compute()
        await cache.set(key, total, self.count_cache_ttl)
        return total

    def _count_cache_model_key(self) -> str:
        """Module-qualified so same-named models in different modules never share entries."""
        return f"{self.model.__module__}.{self.model.__qualname__}"

    async def invalidate_count_cache(self) -> None:
        """Drop this model's cached totals; call it after writes made outside the adapter."""
        if self.count_cache is not None:
            await self.count_cache.invalidate_model(self._count_cache_model_key())

    def for_model(self, model: Any) -> BaseAdapter:
        """Return a new adapter of this same class for ``model``.

        Carries over this adapter's ``engine`` and ``session_factory`` so the new
        adapter shares the same database connection seam — used to construct inline
        / related-model adapters instead of reaching for a concrete adapter class
        and ``self.engine`` directly (which breaks a ``session_factory=``-only
        admin).

        ``session_factory`` is forwarded only when set, so a third-party
        ``BaseAdapter`` subclass that still uses the pre-0.5.8, engine-only
        ``__init__(self, model, engine)`` signature keeps working unchanged
        (it never sees an unexpected ``session_factory`` keyword).
        """
        kwargs: dict[str, Any] = {"engine": self.engine}
        if self.session_factory is not None:
            kwargs["session_factory"] = self.session_factory
        return type(self)(model, **kwargs)

    def datetime_kind(self, field: str) -> DateTimeKind | None:
        """Return whether ``field`` stores timezone-aware or naive datetimes.

        The default reads the pydantic annotation only: ``AwareDatetime`` is
        ``"aware"``, any other datetime is ``"naive"`` and non-datetime or unknown
        fields return ``None``. ORM adapters override this with column introspection.
        """
        try:
            model_fields = schema_for(self.model).model_fields
        except TypeError:  # a model class the schema registry does not know
            return None
        if field not in model_fields:
            return None
        return annotation_datetime_kind(model_fields[field].annotation)

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
        scoped = scoped_queryset_filters(self.model, request)
        if not scoped:
            return result
        return {**result, **scoped}

    async def ensure_inline_rows_owned(
        self,
        spec: InlineModelSpec,
        rows: builtins.list[dict[str, Any]],
        parent_pk: Any,
    ) -> None:
        """Raise :class:`InlineRowNotOwnedError` unless every ``_pk`` is a child of the parent.

        Must run before any write. A submitted child pk is never trusted on its
        own: it must be an existing child (``fk_field == parent_pk``) of the
        parent being saved. Adapters provide the lookup via :meth:`inline_child_pks`,
        which returns DB-typed keys (e.g. ``uuid.UUID`` for a UUID-keyed child).

        A submitted ``_pk`` is a key already parsed by ``InlineFormset`` with the
        child's codec, or whatever a direct adapter caller passes. It is parsed
        (again) through the *child* model's own primary-key codec (not the
        parent's) before comparing against ``owned``, so a
        UUID-keyed child's submitted ``str(uuid)`` compares equal to the
        ``uuid.UUID`` instances ``inline_child_pks`` returns, instead of every
        row with an existing ``_pk`` being rejected as foreign.
        """
        submitted_raw = [row["_pk"] for row in rows if row.get("_pk") is not None]
        if not submitted_raw:
            return
        child_pk = self.for_model(spec.model).pk

        def _parse_or_foreign(raw: Any) -> tuple[Any, Any]:
            # Cannot possibly be a real child key — reject it as foreign
            # rather than letting the parse error bubble up as a 500.
            try:
                return (child_pk.parse(raw), _FOREIGN)
            except InvalidPrimaryKey:
                return (_FOREIGN, raw)

        parsed_or_foreign = [_parse_or_foreign(raw) for raw in submitted_raw]
        submitted = {parsed for parsed, _ in parsed_or_foreign if parsed is not _FOREIGN}
        foreign = {raw for _, raw in parsed_or_foreign if raw is not _FOREIGN}
        owned = await self.inline_child_pks(spec, parent_pk) if parent_pk is not None else set()
        foreign |= submitted - owned
        if foreign:
            raise InlineRowNotOwnedError(
                f"Inline rows {sorted(map(str, foreign))} do not belong to this parent"
            )

    async def inline_child_pks(self, spec: InlineModelSpec, parent_pk: Any) -> set[Any]:  # noqa: ARG002
        """Return the primary keys of ``spec.model`` rows whose FK points at ``parent_pk``.

        Adapters that support inline formsets override this. The default vouches
        for no key, so any submitted child pk is rejected.
        """
        return set()

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
        filters: Mapping[str, Any] | Sequence[FilterCondition] | None = None,
        order_by: str | None = None,
        search_fields: builtins.list[str] | None = None,
    ) -> tuple[builtins.list[Any], int]:
        """
        Retrieves a list of objects with optional pagination, searching, and filtering.

        Args:
            page: The page number for pagination.
            page_size: The number of items per page.
            search: A search query to filter the results.
            filters: Either the legacy ``{column: value}`` equality mapping, or a
                ``Sequence[FilterCondition]`` (``core/filtering.py``) carrying
                ``exact``/``gte``/``lte``/``in``/``isnull`` predicates.
                Implementations resolve either form through
                :func:`hyperadmin.core.filtering.normalize_filters`.
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
        label_fn: Callable[[Any], str] | None = None,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        """Return paginated, searchable choices for a relation field.

        Args:
            field: The relation field name on this adapter's model.
            q: Optional search string (ILIKE match on string columns).
            limit: Max results to return. Must not exceed 200.
            offset: Number of rows to skip for pagination.
            label_fn: Renders each target row's option label (``relation_display``);
                defaults to :func:`~hyperadmin.core.display.get_display_name`.
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
        filters: Mapping[str, Any] | Sequence[FilterCondition] | None = None,
        order_by: str | None = None,
    ) -> ListEnvelope:
        """Return a paginated list wrapped in a ``ListEnvelope``.

        Delegates to ``self.list()`` for data retrieval, then serialises each
        record via ``self.to_dict()``.

        Args:
            page: The page number for pagination.
            page_size: The number of items per page.
            search: A search query to filter the results.
            filters: Either the legacy ``{column: value}`` equality mapping, or a
                ``Sequence[FilterCondition]`` (``core/filtering.py``) carrying
                ``exact``/``gte``/``lte``/``in``/``isnull`` predicates.
                Implementations resolve either form through
                :func:`hyperadmin.core.filtering.normalize_filters`.
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
