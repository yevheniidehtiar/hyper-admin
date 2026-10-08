import builtins
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel

from hyperadmin.adapters._search import detect_search_columns
from hyperadmin.core.adapters import BaseAdapter, scoped_queryset_filters
from hyperadmin.core.choices import ChoiceItem
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.sensitive import is_sensitive

_MAX_CHOICES_LIMIT = 200


class SQLAlchemyAdapter(BaseAdapter):
    def __init__(self, model: type[SQLModel], engine: AsyncEngine) -> None:
        super().__init__(model=model, engine=engine)
        self.inspector = inspect(model)
        if self.inspector is None:
            raise ValueError("Could not inspect model. Is it a valid SQLAlchemy model?")

    async def get(self, pk: Any) -> Any:
        """Retrieve an object by primary key, applying any ``get_queryset`` filters.

        Filters returned by :meth:`get_queryset` are ANDed with the primary-key
        predicate so excluded rows resolve to ``None`` (not raised).
        """
        queryset_filters = self._resolve_queryset_filters()
        async with AsyncSession(self.engine) as session:
            if not queryset_filters:
                return await session.get(self.model, pk)
            assert self.inspector is not None  # noqa: S101 — validated in __init__
            pk_col = self.inspector.primary_key[0]
            conditions = [pk_col == pk]
            for key, value in queryset_filters.items():
                conditions.append(getattr(self.model, key) == value)
            query = select(self.model).where(and_(*conditions))
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        search_fields: list[str] | None = None,
    ) -> tuple[list[Any], int]:
        queryset_filters = self._resolve_queryset_filters()
        where_conditions = [
            getattr(self.model, key) == value for key, value in queryset_filters.items()
        ]
        if filters:
            for key, value in filters.items():
                where_conditions.append(getattr(self.model, key) == value)

        if search and self.inspector:
            fields_to_search = search_fields or detect_search_columns(self.model, self.inspector)
            search_clauses = [
                getattr(self.model, name).ilike(f"%{search}%")
                for name in fields_to_search
                if getattr(self.model, name, None) is not None
            ]
            if search_clauses:
                where_conditions.append(or_(*search_clauses))

        items_query = select(self.model)
        if where_conditions:
            items_query = items_query.where(and_(*where_conditions))

        count_query = select(func.count()).select_from(self.model)
        if where_conditions:
            count_query = count_query.where(and_(*where_conditions))

        if order_by:
            if order_by.startswith("-"):
                items_query = items_query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                items_query = items_query.order_by(getattr(self.model, order_by).asc())

        paginated_items_query = items_query.offset((page - 1) * page_size).limit(page_size)

        async with AsyncSession(self.engine) as session:
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar_one()

            items_result = await session.execute(paginated_items_query)
            items = items_result.scalars().all()

            return list(items), total_count

    async def create(self, data: dict[str, Any]) -> Any:
        db_obj = self.model.model_validate(data)
        async with AsyncSession(self.engine) as session:
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
        return db_obj

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        async with AsyncSession(self.engine) as session:
            db_obj = await session.get(self.model, pk)
            if db_obj:
                for key, value in data.items():
                    setattr(db_obj, key, value)
                session.add(db_obj)
                await session.commit()
                await session.refresh(db_obj)
            return db_obj

    async def delete(self, pk: Any) -> None:
        async with AsyncSession(self.engine) as session:
            db_obj = await session.get(self.model, pk)
            if db_obj:
                await session.delete(db_obj)
                await session.commit()

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        if not self.inspector or not hasattr(self.model, field):
            return []
        queryset_filters = self._resolve_queryset_filters()
        async with AsyncSession(self.engine) as session:
            query = (
                select(self.model)
                .where(self.inspector.primary_key[0] == pk)
                .options(selectinload(getattr(self.model, field)))
            )
            for key, value in queryset_filters.items():
                query = query.where(getattr(self.model, key) == value)
            result = await session.execute(query)
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                return []

            try:
                related = getattr(db_obj, field)
                if related is None:
                    return []
                if isinstance(related, list):
                    return list(related)
                return [related]
            except AttributeError:
                return []

    async def get_schema(self) -> dict[str, Any]:
        return self.model.model_json_schema()

    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        """Return paginated, searchable choices for a relation field.

        Performs a single SELECT on the related model — no N+1.
        """
        if limit > _MAX_CHOICES_LIMIT:
            raise ValueError(f"limit {limit} exceeds maximum of {_MAX_CHOICES_LIMIT}")

        if not self.inspector:
            return []

        target_model = None
        for rel in self.inspector.relationships:
            if rel.key == field:
                target_model = rel.mapper.class_
                break

        if target_model is None:
            return []

        target_inspector = inspect(target_model)
        async with AsyncSession(self.engine) as session:
            query = select(target_model)

            if q:
                # Never match on sensitive columns (q would be a substring oracle).
                str_cols = [
                    getattr(target_model, name)
                    for name in detect_search_columns(target_model, target_inspector)
                ]
                if str_cols:
                    query = query.where(or_(*[c.ilike(f"%{q}%") for c in str_cols[:3]]))

            # Row scoping of the target model's admin (tenant / RLS) always applies.
            for key, value in scoped_queryset_filters(target_model).items():
                query = query.where(getattr(target_model, key) == value)

            # Cascade filters: the view forwards only keys declared by the widget.
            for key, value in filters.items():
                if hasattr(target_model, key) and not is_sensitive(key):
                    query = query.where(getattr(target_model, key) == value)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            items = result.scalars().all()

        return [
            ChoiceItem(
                value=str(getattr(item, "id", "")),
                label=str(item),
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

        Args:
            spec: The ``InlineModelSpec`` describing the related model and FK field.
            rows: Validated row dicts, each optionally containing ``_pk`` (for
                update/delete) and ``_delete`` (for deletion).
            parent_pk: The primary key of the parent object to associate new rows with.

        Raises:
            InlineRowNotOwned: Before any write, when a submitted ``_pk`` is not an
                existing child of ``parent_pk``.
        """
        await self.ensure_inline_rows_owned(spec, rows, parent_pk)
        inline_adapter = SQLAlchemyAdapter(spec.model, self.engine)
        pk_attrs = {col.key for col in inspect(spec.model).primary_key}
        for row in rows:
            row_pk = row.get("_pk")
            if row.get("_delete") and row_pk is not None:
                await inline_adapter.delete(pk=row_pk)
            elif row_pk is not None:
                # Keys are immutable and the row stays attached to its parent.
                row_data = {
                    k: v
                    for k, v in row.items()
                    if k not in ("_pk", "_delete", spec.fk_field) and k not in pk_attrs
                }
                await inline_adapter.update(pk=row_pk, data=row_data)
            elif not row.get("_delete"):
                row_data = {k: v for k, v in row.items() if k not in ("_pk", "_delete")}
                row_data[spec.fk_field] = parent_pk
                await inline_adapter.create(data=row_data)

    async def inline_child_pks(self, spec: InlineModelSpec, parent_pk: Any) -> set[Any]:
        """Return the primary keys of ``spec.model`` rows owned by ``parent_pk``."""
        pk_col = inspect(spec.model).primary_key[0]
        async with AsyncSession(self.engine) as session:
            result = await session.execute(
                select(pk_col).where(getattr(spec.model, spec.fk_field) == parent_pk)
            )
            return set(result.scalars().all())
