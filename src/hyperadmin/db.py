from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

sqlite_file_name = "db.sqlite3"
sqlite_url = f"sqlite+aiosqlite:///{sqlite_file_name}"

engine = create_async_engine(sqlite_url, echo=True)


async def create_db_and_tables():
    """Creates the database and all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
