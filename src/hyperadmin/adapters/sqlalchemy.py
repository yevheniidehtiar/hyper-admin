import builtins
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import String
from sqlmodel import AutoString, SQLModel

from hyperadmin.core.adapters import BaseAdapter


class SQLAlchemyAdapter(BaseAdapter):
    def __init__(self, model: type[SQLModel], engine: AsyncEngine) -> None:
        self.model = model
        self.engine = engine
        self.inspector = inspect(model)
        if self.inspector is None:
            raise ValueError("Could not inspect model. Is it a valid SQLAlchemy model?")

    async def get(self, pk: Any) -> Any:
        async with AsyncSession(self.engine) as session:
            return await session.get(self.model, pk)

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
    ) -> tuple[list[Any], int]:
        where_conditions = []
        if filters:
            for key, value in filters.items():
                where_conditions.append(getattr(self.model, key) == value)

        if search and self.inspector:
            search_clauses = []
            for column in self.inspector.c:
                if isinstance(column.type, AutoString | String):
                    search_clauses.append(getattr(self.model, column.name).ilike(f"%{search}%"))
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
        if not self.inspector:
            return []
        async with AsyncSession(self.engine) as session:
            query = (
                select(self.model)
                .where(self.inspector.primary_key[0] == pk)
                .options(selectinload(getattr(self.model, field)))
            )
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
