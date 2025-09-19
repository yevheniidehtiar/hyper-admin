from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

from examples.models import User
from hyperadmin.main import Admin

# 1. Create a database engine
engine = create_async_engine(
    "sqlite+aiosqlite:///simple_app.db", connect_args={"check_same_thread": False}
)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        result = await session.execute(select(User))
        if not result.first():
            session.add(User(name="Alice", email="alice@example.com"))
            session.add(User(name="Bob", email="bob@example.com"))
            session.add(User(name="Charlie", email="charlie@example.com"))
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    await create_db_and_tables()
    yield


# 2. Create a FastAPI app and an Admin instance with auto-discovery
app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/hyperadmin/static"), name="static")
admin = Admin(app, discover_apps=["examples"])

# 3. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
