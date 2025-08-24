from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine, select

from hyperadmin.main import Admin
from hyperadmin.views import ModelView


# 1. Define a SQLModel model
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str


# 2. Create a database engine
engine = create_engine("sqlite:///simple_app.db", connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            session.add(User(name="Alice", email="alice@example.com"))
            session.add(User(name="Bob", email="bob@example.com"))
            session.add(User(name="Charlie", email="charlie@example.com"))
            session.commit()


# 3. Create a ModelView for the User model
class UserAdmin(ModelView):
    model = User


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    create_db_and_tables()
    yield


# 4. Create a FastAPI app and an Admin instance
app = FastAPI(lifespan=lifespan)
admin = Admin(app)


# 5. Register the ModelView
admin.register(UserAdmin)

# 6. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
