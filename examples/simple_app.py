from fastapi import FastAPI
from pydantic import BaseModel

from hyperadmin.main import Admin
from hyperadmin.views import ModelView


# 1. Define a Pydantic model
class User(BaseModel):
    id: int
    name: str
    email: str


# 2. Create some in-memory data
users_data = [
    User(id=1, name="Alice", email="alice@example.com"),
    User(id=2, name="Bob", email="bob@example.com"),
    User(id=3, name="Charlie", email="charlie@example.com"),
]


# 3. Create a ModelView for the User model
class UserAdmin(ModelView):
    model = User
    data = users_data


# 4. Create a FastAPI app and an Admin instance
app = FastAPI()
admin = Admin(app)

# 5. Register the ModelView
admin.register(UserAdmin)

# 6. Mount the admin interface
admin.mount(path="/admin")


@app.get("/")
def read_root():
    return {"message": "Go to /admin/user to see the admin interface."}
