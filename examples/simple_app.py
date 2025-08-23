from fastapi import FastAPI
from sqlmodel import Field, SQLModel, Session, create_engine

from hyperadmin.main import Admin
from hyperadmin.views import ModelView


# 1. Define a SQLModel model
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str


# 2. Create a database engine
engine = create_engine("sqlite:///example.db", connect_args={"check_same_thread": False})


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(User).first():
            session.add(User(name="Alice", email="alice@example.com"))
            session.add(User(name="Bob", email="bob@example.com"))
            session.add(User(name="Charlie", email="charlie@example.com"))
            session.commit()


# 3. Create a ModelView for the User model
class UserAdmin(ModelView):
    model = User


# 4. Create a FastAPI app and an Admin instance
app = FastAPI()
admin = Admin(app, engine=engine)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# 5. Register the ModelView
admin.register(UserAdmin)

# 6. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
