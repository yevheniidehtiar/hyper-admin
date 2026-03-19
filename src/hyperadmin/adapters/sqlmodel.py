import builtins
from typing import Any

from sqlalchemy import func, inspect, or_
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select

from hyperadmin.core.adapters import BaseAdapter


class SQLModelAdapter(BaseAdapter):
    """
    Data adapter for SQLModel.
    """

    def __init__(self, model: type[SQLModel], engine: AsyncEngine):
        super().__init__(model, engine)

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

            # Apply searching
            if search:
                # For now, we'll search on name and email.
                # This should be made more generic in a real application.
                query = query.where(
                    or_(
                        getattr(self.model, "name").ilike(f"%{search}%"),
                        getattr(self.model, "email").ilike(f"%{search}%"),
                    )
                )

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
