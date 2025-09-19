from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, create_engine, select

from examples.models import User
from hyperadmin.main import Admin

# 1. Create a database engine
engine = create_engine("sqlite:///simple_app.db", connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            session.add(User(name="Alice", email="alice@example.com"))
            session.add(User(name="Bob", email="bob@example.com"))
            session.add(User(name="Charlie", email="charlie@example.com"))
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    create_db_and_tables()
    yield


# 2. Create a FastAPI app and an Admin instance with auto-discovery
app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/hyperadmin/static"), name="static")
admin = Admin(app)

# 3. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
