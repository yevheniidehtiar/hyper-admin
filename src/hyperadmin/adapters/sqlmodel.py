import builtins
import warnings
from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, inspect, literal, or_, tuple_
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select

from hyperadmin.adapters._estimate import estimate_table_rows
from hyperadmin.adapters._filter_clause import build_clauses
from hyperadmin.adapters._occ import claim_version
from hyperadmin.adapters._relation_loading import relation_load_options
from hyperadmin.adapters._search import contains_clause, detect_search_columns
from hyperadmin.adapters.introspection import coerce_column_value, introspect_primary_key
from hyperadmin.adapters.introspection import datetime_kind as _introspect_datetime_kind
from hyperadmin.core.adapters import (
    BaseAdapter,
    Cursor,
    CursorDirection,
    InvalidCursorError,
    KeysetFallbackWarning,
    ListResult,
    SessionFactory,
    decode_cursor,
    encode_cursor,
    scoped_queryset_filters,
)
from hyperadmin.core.choices import ChoiceItem
from hyperadmin.core.display import get_display_name
from hyperadmin.core.filtering import FilterCondition, normalize_filters
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.primary_key import InvalidPrimaryKey
from hyperadmin.core.sensitive import effective_sensitive_field_names

if TYPE_CHECKING:
    from sqlalchemy.orm import Mapper

    from hyperadmin.core.timezones import DateTimeKind

_MAX_CHOICES_LIMIT = 200


class SQLModelAdapter(BaseAdapter):
    """
    Data adapter for SQLModel.
    """

    def __init__(
        self,
        model: type[SQLModel],
        engine: AsyncEngine | None = None,
        *,
        session_factory: SessionFactory | None = None,
    ):
        super().__init__(model, engine, session_factory=session_factory)
        self.inspector = inspect(model)
        self.pk = introspect_primary_key(model)

    def datetime_kind(self, field: str) -> "DateTimeKind | None":
        """Return the column-introspected datetime kind for ``field``.

        Overrides :meth:`BaseAdapter.datetime_kind` (annotation-only) with the
        full rule set in :func:`hyperadmin.adapters.introspection.datetime_kind`,
        which also inspects the mapped column type.
        """
        try:
            return _introspect_datetime_kind(self.model, field)
        except KeyError:
            return None

    async def get(self, pk: Any, *, load_relations: builtins.list[str] | None = None) -> Any:
        """
        Retrieves a single object by its primary key.

        Any filters returned by :meth:`get_queryset` are merged into the WHERE clause
        before the primary-key predicate so excluded rows resolve to ``None``.

        Args:
            pk: The primary key of the object to retrieve.
            load_relations: Relations to eager-load. ``None`` loads every relation,
                ``[]`` none, and a list exactly those; an unknown name raises
                :class:`ValueError`.

        Returns:
            The retrieved object, or ``None`` if not found, or if ``pk`` does not
            parse as this model's key type.

        Raises:
            NotImplementedError: For a composite primary key.
        """
        try:
            parsed_pk = self.pk.parse(pk)
        except InvalidPrimaryKey:
            return None
        queryset_filters = self._resolve_queryset_filters()
        async with self._session() as session:
            if load_relations is None:
                load_relations = [rel.key for rel in inspect(self.model).relationships]
            options = relation_load_options(self.model, load_relations)
            query = (
                select(self.model)
                .where(getattr(self.model, self.pk.attr) == parsed_pk)
                .options(*options)
            )
            for key, value in queryset_filters.items():
                query = query.where(getattr(self.model, key) == value)
            result = await session.execute(query)
            return result.unique().scalar_one_or_none()

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: Mapping[str, Any] | Sequence[FilterCondition] | None = None,
        order_by: str | None = None,
        search_fields: list[str] | None = None,
        load_relations: builtins.list[str] | None = None,
    ) -> tuple[list[Any], int]:
        """
        Retrieves a list of objects with optional pagination, searching, and filtering.

        ``load_relations`` names the relations to eager-load with ``selectinload``;
        ``None`` and ``[]`` load none, and an unknown name raises :class:`ValueError`.

        Filters returned by :meth:`get_queryset` are applied **before** any
        view-layer ``filters`` so they cannot be bypassed. The same predicates are
        included in the count query, keeping pagination math consistent.

        ``filters`` accepts either the legacy ``{column: value}`` equality
        mapping or a ``Sequence[FilterCondition]``; both are resolved through
        :func:`hyperadmin.core.filtering.normalize_filters` and compiled to
        clauses via :mod:`hyperadmin.adapters._filter_clause`, shared with
        :class:`~hyperadmin.adapters.sqlalchemy.SQLAlchemyAdapter`.
        """
        queryset_filters = self._resolve_queryset_filters()
        async with self._session() as session:
            query = self._scoped_query(queryset_filters, filters, search, search_fields)

            if load_relations:
                query = query.options(*relation_load_options(self.model, load_relations))

            # Apply ordering
            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(getattr(self.model, order_by[1:]).desc())
                else:
                    query = query.order_by(getattr(self.model, order_by).asc())

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())

            async def compute_total() -> int:
                return (await session.execute(count_query)).scalar_one()

            total_count = await self._cached_count(
                compute_total,
                filters=normalize_filters(filters),
                search=search,
                search_fields=search_fields,
                queryset_filters=queryset_filters,
            )

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Get the rows
            results = await session.execute(query)
            return list(results.unique().scalars().all()), total_count

    def _scoped_query(
        self,
        queryset_filters: Mapping[str, Any],
        filters: Mapping[str, Any] | Sequence[FilterCondition] | None,
        search: str | None,
        search_fields: builtins.list[str] | None,
    ) -> Any:
        """Return ``select(model)`` narrowed by queryset, view-layer and search predicates.

        Queryset hook filters (RLS / tenant scoping) come first so they cannot be
        bypassed; ``filters`` (a legacy dict or a ``Sequence[FilterCondition]``) are
        compiled through the clause builder shared with ``SQLAlchemyAdapter``.
        """
        query = select(self.model)
        for key, value in queryset_filters.items():
            query = query.where(getattr(self.model, key) == value)
        for clause in build_clauses(self.model, normalize_filters(filters)):
            query = query.where(clause)
        if search:
            fields_to_search = (
                search_fields if search_fields is not None else self._detect_search_fields()
            )
            conditions = [
                contains_clause(col, search)
                for col in (getattr(self.model, name, None) for name in fields_to_search)
                if col is not None
            ]
            if conditions:
                query = query.where(or_(*conditions))
        return query

    async def list_paginated(  # noqa: PLR0913 - mirrors BaseAdapter.list_paginated
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        cursor: str | None = None,
        search: str | None = None,
        filters: Mapping[str, Any] | Sequence[FilterCondition] | None = None,
        order_by: str | None = None,
        search_fields: builtins.list[str] | None = None,
        load_relations: builtins.list[str] | None = None,
    ) -> ListResult:
        """Return one page of the list; keyset-paged when :attr:`pagination_mode` is ``"cursor"``.

        In cursor mode the page is ``WHERE (sort_col, pk) > (cursor key) ORDER BY sort_col,
        pk LIMIT page_size + 1`` (``<`` and ``DESC`` for a descending sort, reversed for a
        ``"prev"`` cursor): no ``OFFSET`` and no ``count(*)``, so ``total`` is ``None``. The
        primary key breaks ties on a non-unique sort column, and ``order_by=None`` sorts by
        the primary key. ``get_queryset()`` filters, ``filters`` and ``search`` apply to
        every page, so a cursor never widens the row set.

        A sort that keyset cannot page deterministically is served as an ``OFFSET`` page
        (``page`` applies, ``total`` is counted) with a :class:`KeysetFallbackWarning`:
        a composite primary key, a sort target that is not a mapped column, or a nullable
        sort column that holds NULLs within the filtered rows. ``"offset"`` mode
        delegates to :meth:`BaseAdapter.list_paginated`.

        Raises:
            InvalidCursorError: ``cursor`` is malformed, tampered with, or its key does
                not convert to the primary-key and sort-column types.
        """
        if self.pagination_mode != "cursor":
            return await super().list_paginated(
                page=page,
                page_size=page_size,
                cursor=cursor,
                search=search,
                filters=filters,
                order_by=order_by,
                search_fields=search_fields,
                load_relations=load_relations,
            )
        decoded = decode_cursor(cursor) if cursor is not None else None
        descending = (order_by or "").startswith("-")
        sort_attr = (order_by or "").lstrip("-") or self.pk.attr
        queryset_filters = self._resolve_queryset_filters()
        scoped = self._scoped_query(queryset_filters, filters, search, search_fields)
        sort_column = cast("Mapper[Any]", self.inspector).columns.get(sort_attr)
        reason = self._keyset_blocker(sort_attr, sort_column)
        async with self._session() as session:
            if reason is None and sort_column is not None and sort_column.nullable:
                pk_col = getattr(self.model, self.pk.attr)
                null_probe = (
                    scoped.with_only_columns(pk_col)
                    .where(getattr(self.model, sort_attr).is_(None))
                    .limit(1)
                )
                if (await session.execute(null_probe)).first() is not None:
                    reason = f"sort column {sort_attr!r} holds NULLs"
            if reason is not None:
                warnings.warn(
                    f"{type(self).__name__}: cannot page {self.model.__name__} by keyset "
                    f"({reason}); serving an OFFSET page instead",
                    KeysetFallbackWarning,
                    stacklevel=2,
                )
            else:
                return await self._keyset_page(
                    session,
                    scoped,
                    sort_attr=sort_attr,
                    descending=descending,
                    cursor=decoded,
                    page_size=page_size,
                    load_relations=load_relations,
                )
        items, total = await self.list(
            page=page,
            page_size=page_size,
            search=search,
            filters=filters,
            order_by=order_by,
            search_fields=search_fields,
            load_relations=load_relations,
        )
        return ListResult(
            items=items,
            total=total,
            has_next=page * page_size < total,
            has_prev=page > 1,
        )

    def _keyset_blocker(self, sort_attr: str, sort_column: Any) -> str | None:
        """Return why this list cannot be keyset-paged before touching the database."""
        if self.pk.composite:
            return "composite primary key"
        if sort_column is None:
            return f"{sort_attr!r} is not a mapped column"
        return None

    async def _keyset_page(
        self,
        session: Any,
        scoped: Any,
        *,
        sort_attr: str,
        descending: bool,
        cursor: Cursor | None,
        page_size: int,
        load_relations: builtins.list[str] | None,
    ) -> ListResult:
        """Fetch one keyset page of ``scoped`` after (or before) ``cursor``.

        Fetches ``page_size + 1`` rows: the extra row only signals that another page
        exists in the paging direction and is not returned.
        """
        pk_attr = self.pk.attr
        pk_col = getattr(self.model, pk_attr)
        sort_col = getattr(self.model, sort_attr)
        on_pk = sort_attr == pk_attr
        backwards = cursor is not None and cursor.direction == "prev"
        # Scanning towards smaller keys: a descending sort paged forwards, or an
        # ascending sort paged backwards.
        scan_desc = descending != backwards
        query = scoped
        if cursor is not None:
            key_pk, key_sort = self._cursor_key(cursor, sort_attr)
            if on_pk:
                query = query.where(pk_col < key_pk if scan_desc else pk_col > key_pk)
            else:
                # Bind the key with the column types so enums, UUIDs and datetimes
                # go through the columns' bind processors.
                row = tuple_(sort_col, pk_col)
                bound = tuple_(literal(key_sort, sort_col.type), literal(key_pk, pk_col.type))
                query = query.where(row < bound if scan_desc else row > bound)
        order_cols = [pk_col] if on_pk else [sort_col, pk_col]
        query = query.order_by(*(c.desc() if scan_desc else c.asc() for c in order_cols))
        if load_relations:
            query = query.options(*relation_load_options(self.model, load_relations))
        rows = list((await session.execute(query.limit(page_size + 1))).unique().scalars())
        more = len(rows) > page_size
        items = rows[:page_size]
        if backwards:
            items.reverse()
        if not items:
            return ListResult(items=[], total=None)
        # Moving forwards there is a page behind the cursor; moving backwards there is
        # one ahead of it. The extra row tells whether one exists the other way.
        has_next = more if not backwards else True
        has_prev = cursor is not None if not backwards else more
        return ListResult(
            items=items,
            total=None,
            next_cursor=self._row_cursor(items[-1], sort_attr, "next") if has_next else None,
            prev_cursor=self._row_cursor(items[0], sort_attr, "prev") if has_prev else None,
            has_next=has_next,
            has_prev=has_prev,
        )

    def _row_cursor(self, row: Any, sort_attr: str, direction: CursorDirection) -> str:
        """Encode the cursor pointing at ``row``; enum values travel as member names."""
        pk_value = getattr(row, self.pk.attr)
        sort_value = getattr(row, sort_attr)
        if isinstance(sort_value, Enum):
            sort_value = sort_value.name
        return encode_cursor(pk_value, sort_value, direction)

    def _cursor_key(self, cursor: Cursor, sort_attr: str) -> tuple[Any, Any]:
        """Convert a decoded cursor key back to the primary-key and sort-column types.

        Raises:
            InvalidCursorError: A key value is not a scalar or does not convert.
        """
        raw_pk, raw_sort = cursor.key
        if isinstance(raw_pk, list | dict) or isinstance(raw_sort, list | dict):
            raise InvalidCursorError("Invalid pagination cursor")
        try:
            return self.pk.parse(raw_pk), coerce_column_value(self.inspector, sort_attr, raw_sort)
        except (InvalidPrimaryKey, ValueError) as exc:
            raise InvalidCursorError("Invalid pagination cursor") from exc

    def _detect_search_fields(self) -> builtins.list[str]:
        """Detect non-sensitive string columns on the model for search fallback."""
        return detect_search_columns(self.model, self.inspector)

    async def estimate_row_count(self) -> int:
        """Approximate whole-table row count; see :func:`estimate_table_rows`."""
        async with self._session() as session:
            rows, self.estimates_row_count = await estimate_table_rows(
                session, self.model.__table__
            )
        return rows

    async def create(self, data: dict[str, Any]) -> Any:
        """
        Creates a new object.

        Args:
            data: A dictionary of data for the new object.

        Returns:
            The created object.
        """
        async with self._session() as session:
            db_obj = self.model(**data)
            session.add(db_obj)
            await session.commit()
            await self.invalidate_count_cache()
            await session.refresh(db_obj)
            return db_obj

    async def update(
        self, pk: Any, data: dict[str, Any], *, expected_version: Any | None = None
    ) -> Any:
        """
        Updates an existing object.

        Primary-key attributes in ``data`` are dropped before assignment, so the
        key is always immutable through this method.

        Args:
            pk: The primary key of the object to update.
            data: A dictionary of data to update the object with.

        Returns:
            The updated object.

        Raises:
            InvalidPrimaryKey: If ``pk`` does not parse as this model's key type.
            NotImplementedError: For a composite primary key.
            StaleRecordError: ``expected_version`` no longer matches the stored row.
        """
        parsed_pk = self.pk.parse(pk)
        data = {key: value for key, value in data.items() if key not in self.pk.attrs}
        async with self._session() as session:
            if expected_version is not None and self.version_field:
                # Raises StaleRecordError before any other column is written.
                db_obj = await claim_version(
                    session,
                    self.model,
                    self.pk.attr,
                    parsed_pk,
                    self.version_field,
                    expected_version,
                )
                data = {k: v for k, v in data.items() if k != self.version_field}
            else:
                db_obj = await session.get(self.model, parsed_pk)
            if db_obj:
                for key, value in data.items():
                    setattr(db_obj, key, value)
                session.add(db_obj)
                await session.commit()
                await self.invalidate_count_cache()
                await session.refresh(db_obj)
            return db_obj

    async def delete(self, pk: Any) -> None:
        """
        Deletes an object.

        Args:
            pk: The primary key of the object to delete.

        Raises:
            InvalidPrimaryKey: If ``pk`` does not parse as this model's key type.
            NotImplementedError: For a composite primary key.
        """
        parsed_pk = self.pk.parse(pk)
        async with self._session() as session:
            db_obj = await session.get(self.model, parsed_pk)
            if db_obj:
                await session.delete(db_obj)
                await session.commit()
                await self.invalidate_count_cache()

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        """
        Retrieves related objects for a given object and field.

        Args:
            pk: The primary key of the object.
            field: The name of the related field.

        Returns:
            A list of related objects, or ``[]`` if not found, or if ``pk`` does
            not parse as this model's key type.

        Raises:
            NotImplementedError: For a composite primary key.
        """
        try:
            parsed_pk = self.pk.parse(pk)
        except InvalidPrimaryKey:
            return []
        queryset_filters = self._resolve_queryset_filters()
        async with self._session() as session:
            query = (
                select(self.model)
                .where(getattr(self.model, self.pk.attr) == parsed_pk)
                .options(selectinload(getattr(self.model, field)))
            )
            for key, value in queryset_filters.items():
                query = query.where(getattr(self.model, key) == value)
            result = await session.execute(query)
            db_obj = result.unique().scalar_one_or_none()
            if db_obj:
                return getattr(db_obj, field)
            return []

    async def get_schema(self) -> dict[str, Any]:
        """
        Returns the JSON schema for the model.

        Returns:
            A dictionary representing the JSON schema.
        """
        return self.model.model_json_schema()

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

        Performs a single SELECT on the related model — no N+1.
        """
        if limit > _MAX_CHOICES_LIMIT:
            raise ValueError(f"limit {limit} exceeds maximum of {_MAX_CHOICES_LIMIT}")

        mapper = inspect(self.model)
        target_model = None
        for rel in mapper.relationships:
            if rel.key == field:
                target_model = rel.mapper.class_
                break

        if target_model is None:
            return []

        target_inspector = inspect(target_model)
        target_pk = introspect_primary_key(target_model)
        async with self._session() as session:
            query = select(target_model)

            if q:
                # Never match on sensitive columns (q would be a substring oracle).
                str_cols = [
                    getattr(target_model, name)
                    for name in detect_search_columns(target_model, target_inspector)
                ]
                if str_cols:
                    query = query.where(or_(*[contains_clause(c, q) for c in str_cols[:3]]))

            # Row scoping of the target model's admin (tenant / RLS) always applies.
            for key, value in scoped_queryset_filters(target_model).items():
                query = query.where(getattr(target_model, key) == value)

            # Cascade filters: the view forwards only keys declared by the widget.
            target_sensitive = effective_sensitive_field_names(target_model)
            for key, value in filters.items():
                if hasattr(target_model, key) and key not in target_sensitive:
                    try:
                        coerced = coerce_column_value(target_inspector, key, value)
                    except ValueError:
                        # An unparseable cascade value (e.g. '' or 'garbage' for a
                        # UUID FK) matches no row rather than raising a 500 — '' is
                        # what a dependent select sends while its parent is blank.
                        return []
                    query = query.where(getattr(target_model, key) == coerced)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            items = result.unique().scalars().all()

        return [
            ChoiceItem(
                # The target's own key codec, not a hardcoded "id": canonical for
                # any key kind (UUIDs become lowercase, hyphenated strings).
                value=target_pk.to_str(target_pk.value_of(item)),
                # Never str(item): SQLModel's default __str__ prints every column.
                label=label_fn(item) if label_fn else get_display_name(item),
                selected=False,
            )
            for item in items
        ]

    async def save_inline_rows(
        self,
        spec: InlineModelSpec,
        rows: builtins.list[dict[str, Any]],
        parent_pk: Any,
    ) -> None:
        """Persist validated inline rows — create, update, or delete as needed.

        A fresh ``SQLModelAdapter`` is constructed for the inline model via
        :meth:`for_model`, so it shares this adapter's ``engine`` or
        ``session_factory``.

        Args:
            spec: The ``InlineModelSpec`` describing the related model and FK field.
            rows: Validated row dicts, each optionally containing ``_pk`` (for
                update/delete) and ``_delete`` (for deletion).
            parent_pk: The primary key of the parent object to associate new rows with.

        Raises:
            InlineRowNotOwnedError: Before any write, when a submitted ``_pk`` is not an
                existing child of ``parent_pk``.
        """
        await self.ensure_inline_rows_owned(spec, rows, parent_pk)
        inline_adapter = self.for_model(spec.model)
        for row in rows:
            row_pk = row.get("_pk")
            if row.get("_delete") and row_pk is not None:
                await inline_adapter.delete(pk=row_pk)
            elif row_pk is not None:
                # Keys are immutable and the row stays attached to its parent;
                # inline_adapter.update() drops any pk attrs from row_data itself.
                row_data = {
                    k: v for k, v in row.items() if k not in ("_pk", "_delete", spec.fk_field)
                }
                await inline_adapter.update(pk=row_pk, data=row_data)
            elif not row.get("_delete"):
                row_data = {k: v for k, v in row.items() if k not in ("_pk", "_delete")}
                row_data[spec.fk_field] = parent_pk
                await inline_adapter.create(data=row_data)

    async def inline_child_pks(self, spec: InlineModelSpec, parent_pk: Any) -> set[Any]:
        """Return the primary keys of ``spec.model`` rows owned by ``parent_pk``."""
        pk_col = inspect(spec.model).primary_key[0]
        async with self._session() as session:
            result = await session.execute(
                select(pk_col).where(getattr(spec.model, spec.fk_field) == parent_pk)
            )
            return set(result.scalars().all())
