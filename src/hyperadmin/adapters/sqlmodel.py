import builtins
from typing import Any

from sqlalchemy import func, inspect, or_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import String
from sqlmodel import AutoString, SQLModel, select

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.choices import ChoiceItem
from hyperadmin.core.inlines import InlineModelSpec

_MAX_CHOICES_LIMIT = 200


class SQLModelAdapter(BaseAdapter):
    """
    Data adapter for SQLModel.
    """

    def __init__(self, model: type[SQLModel], engine: AsyncEngine):
        super().__init__(model, engine)
        self.inspector = inspect(model)

    async def get(self, pk: Any) -> Any:
        """
        Retrieves a single object by its primary key.

        Args:
            pk: The primary key of the object to retrieve.

        Returns:
            The retrieved object, or None if not found.
        """
        async with AsyncSession(self.engine) as session:
            mapper = inspect(self.model)
            options = [selectinload(getattr(self.model, rel.key)) for rel in mapper.relationships]
            query = select(self.model).where(self.model.id == pk).options(*options)
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
        """
        Retrieves a list of objects with optional pagination, searching, and filtering.
        """
        async with AsyncSession(self.engine) as session:
            query = select(self.model)

            # Eagerly load all relationships to avoid DetachedInstanceError
            mapper = inspect(self.model)
            for rel in mapper.relationships:
                query = query.options(selectinload(getattr(self.model, rel.key)))

            # Apply filtering
            if filters:
                for key, value in filters.items():
                    query = query.where(getattr(self.model, key) == value)

            # Apply searching using configured search_fields
            if search:
                fields_to_search = search_fields or self._detect_search_fields()
                if fields_to_search:
                    conditions = []
                    for field_name in fields_to_search:
                        col = getattr(self.model, field_name, None)
                        if col is not None:
                            conditions.append(col.ilike(f"%{search}%"))
                    if conditions:
                        query = query.where(or_(*conditions))

            # Apply ordering
            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(getattr(self.model, order_by[1:]).desc())
                else:
                    query = query.order_by(getattr(self.model, order_by).asc())

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_count_result = await session.execute(count_query)
            total_count = total_count_result.scalar_one()

            # Apply pagination
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size)

            # Get the rows
            results = await session.execute(query)
            return list(results.scalars().all()), total_count

    def _detect_search_fields(self) -> builtins.list[str]:
        """Detect string columns on the model for search fallback."""
        mapper: Any = self.inspector
        return [
            col.key
            for col in mapper.columns
            if isinstance(col.type, (String, AutoString)) and not col.primary_key
        ]

    async def create(self, data: dict[str, Any]) -> Any:
        """
        Creates a new object.

        Args:
            data: A dictionary of data for the new object.

        Returns:
            The created object.
        """
        async with AsyncSession(self.engine) as session:
            db_obj = self.model(**data)
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
            return db_obj

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        """
        Updates an existing object.

        Args:
            pk: The primary key of the object to update.
            data: A dictionary of data to update the object with.

        Returns:
            The updated object.
        """
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
        """
        Deletes an object.

        Args:
            pk: The primary key of the object to delete.
        """
        async with AsyncSession(self.engine) as session:
            db_obj = await session.get(self.model, pk)
            if db_obj:
                await session.delete(db_obj)
                await session.commit()

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        """
        Retrieves related objects for a given object and field.

        Args:
            pk: The primary key of the object.
            field: The name of the related field.

        Returns:
            A list of related objects.
        """
        async with AsyncSession(self.engine) as session:
            query = (
                select(self.model)
                .where(self.model.id == pk)
                .options(selectinload(getattr(self.model, field)))
            )
            result = await session.execute(query)
            db_obj = result.scalar_one_or_none()
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
        async with AsyncSession(self.engine) as session:
            query = select(target_model)

            if q:
                str_cols = [
                    c for c in target_inspector.c if isinstance(c.type, AutoString | String)
                ]
                if str_cols:
                    query = query.where(or_(*[c.ilike(f"%{q}%") for c in str_cols[:3]]))

            for key, value in filters.items():
                if hasattr(target_model, key):
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

        A fresh ``SQLModelAdapter`` is constructed for the inline model using
        this adapter's engine so all operations share the same database connection.

        Args:
            spec: The ``InlineModelSpec`` describing the related model and FK field.
            rows: Validated row dicts, each optionally containing ``_pk`` (for
                update/delete) and ``_delete`` (for deletion).
            parent_pk: The primary key of the parent object to associate new rows with.
        """
        inline_adapter = SQLModelAdapter(spec.model, self.engine)
        for row in rows:
            if row.get("_delete") and row.get("_pk"):
                await inline_adapter.delete(pk=row["_pk"])
            elif "_pk" in row:
                pk = row["_pk"]
                row_data = {k: v for k, v in row.items() if k not in ("_pk", "_delete")}
                await inline_adapter.update(pk=pk, data=row_data)
            else:
                row_data = {k: v for k, v in row.items() if k not in ("_pk", "_delete")}
                row_data[spec.fk_field] = parent_pk
                await inline_adapter.create(data=row_data)
