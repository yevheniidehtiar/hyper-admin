from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select
from starlette.middleware.sessions import SessionMiddleware

from hyperadmin.auth.models import Permission, User, UserPermissions
from hyperadmin.core.app import Admin

# Use a test-specific engine
DB_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DB_URL, connect_args={"check_same_thread": False})


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        # Create a superuser
        admin_user = User(
            username="admin",
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        # Create a regular user
        staff_user = User(
            username="staff",
            email="staff@example.com",
            first_name="Staff",
            last_name="User",
            is_superuser=False,
        )
        # Create a restricted user
        restricted_user = User(
            username="restricted",
            email="restricted@example.com",
            first_name="Restricted",
            last_name="User",
            is_superuser=False,
        )
        session.add_all([admin_user, staff_user, restricted_user])
        await session.commit()

        # Add a permission to staff_user
        perm = Permission(name="Can list user", codename="list_user")
        session.add(perm)
        await session.commit()
        await session.refresh(staff_user)
        await session.refresh(perm)

        up = UserPermissions(user_id=staff_user.id, permission_id=perm.id)
        session.add(up)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="test-secret")

admin = Admin(app, engine=engine, auth_enabled=True)

from hyperadmin.views.dynamic import ModelView


class UserAdmin(ModelView, model=User):
    pass


admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Auth test app"}


@app.get("/login/{username}")
async def login(username: str, request: Request):
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user:
            request.session["user_id"] = user.id
            return {"message": f"Logged in as {username}"}
    return {"message": "User not found"}, 404
