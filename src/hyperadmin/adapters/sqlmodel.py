import builtins
from typing import Any

from sqlalchemy import func, or_, select
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ..core.adapters import BaseAdapter


class SQLModelAdapter(BaseAdapter):
    """
    Data adapter for SQLModel.
    """

    def __init__(self, model: type[SQLModel], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, pk: Any) -> Any:
        """
        Retrieves a single object by its primary key.

        Args:
            pk: The primary key of the object to retrieve.

        Returns:
            The retrieved object, or None if not found.
        """
        return await self.session.get(self.model, pk)

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
        query = select(self.model)

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
        total_count_result = await self.session.exec(count_query)
        total_count = total_count_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Get the rows
        results = await self.session.exec(query)
        return results.scalars().all(), total_count

    async def create(self, data: dict[str, Any]) -> Any:
        """
        Creates a new object.

        Args:
            data: A dictionary of data for the new object.

        Returns:
            The created object.
        """
        db_obj = self.model(**data)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        ...

    async def delete(self, pk: Any) -> None:
        ...

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        ...

    async def get_schema(self) -> dict[str, Any]:
        ...
