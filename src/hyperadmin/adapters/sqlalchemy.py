import asyncio
import builtins
from typing import Any, Type

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import String
from sqlmodel import SQLModel

from hyperadmin.core.adapters import BaseAdapter


class SQLAlchemyAdapter(BaseAdapter):
    def __init__(self, model: Type[SQLModel], engine: Engine) -> None:
        self.model = model
        self.engine = engine
        self.inspector = inspect(self.model)

    async def get(self, pk: Any) -> Any:
        def sync_get() -> Any:
            with Session(self.engine) as session:
                return session.get(self.model, pk)

        return await asyncio.to_thread(sync_get)

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
    ) -> tuple[list[Any], int]:
        def sync_list() -> tuple[list[Any], int]:
            query = select(self.model)
            if filters:
                query = query.filter_by(**filters)

            if search:
                search_clauses = []
                for column in self.inspector.c:
                    if isinstance(column.type, String):
                        search_clauses.append(column.ilike(f"%{search}%"))
                if search_clauses:
                    query = query.where(or_(*search_clauses))

            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(getattr(self.model, order_by[1:]).desc())
                else:
                    query = query.order_by(getattr(self.model, order_by).asc())

            with Session(self.engine) as session:
                count_query = select(func.count()).select_from(query.subquery())
                total_count = session.exec(count_query).one()

                paginated_query = query.offset((page - 1) * page_size).limit(page_size)
                items = session.exec(paginated_query).all()
                return items, total_count

        return await asyncio.to_thread(sync_list)

    async def create(self, data: dict[str, Any]) -> Any:
        def sync_create() -> Any:
            db_obj = self.model.model_validate(data)
            with Session(self.engine) as session:
                session.add(db_obj)
                session.commit()
                session.refresh(db_obj)
            return db_obj

        return await asyncio.to_thread(sync_create)

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        def sync_update() -> Any:
            with Session(self.engine) as session:
                db_obj = session.get(self.model, pk)
                if db_obj:
                    for key, value in data.items():
                        setattr(db_obj, key, value)
                    session.add(db_obj)
                    session.commit()
                    session.refresh(db_obj)
                return db_obj

        return await asyncio.to_thread(sync_update)

    async def delete(self, pk: Any) -> None:
        def sync_delete() -> None:
            with Session(self.engine) as session:
                db_obj = session.get(self.model, pk)
                if db_obj:
                    session.delete(db_obj)
                    session.commit()

        await asyncio.to_thread(sync_delete)

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        def sync_get_related() -> builtins.list[Any]:
            with Session(self.engine) as session:
                db_obj = session.get(self.model, pk)
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

        return await asyncio.to_thread(sync_get_related)

    async def get_schema(self) -> dict[str, Any]:
        return self.model.model_json_schema()
