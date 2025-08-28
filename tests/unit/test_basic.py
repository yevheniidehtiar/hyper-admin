from http import HTTPStatus

import pytest
from examples.models import User
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import delete

from hyperadmin.db import get_session
from hyperadmin.main import Admin
from hyperadmin.views import ModelView

# Create a test-specific app
app = FastAPI()
admin = Admin(app)


class UserAdmin(ModelView):
    model = User


admin.register(UserAdmin)
admin.mount(path="/admin")


client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_users():
    session = next(get_session())
    session.exec(delete(User))
    session.commit()

    session.add(User(name="Alice", email="alice@example.com"))
    session.add(User(name="Bob", email="bob@example.com"))
    session.add(User(name="Charlie", email="charlie@example.com"))
    session.commit()
    return session


def test_get_list_view():
    response = client.get("/admin/user")
    assert response.status_code == HTTPStatus.OK
    assert "User List" in response.text
    assert "Alice" in response.text


def test_get_detail_view():
    response = client.get("/admin/user/1")
    assert response.status_code == HTTPStatus.OK
    assert "User #1" in response.text
    assert "alice@example.com" in response.text


def test_get_detail_view_not_found():
    response = client.get("/admin/user/999")
    assert response.status_code == HTTPStatus.NOT_FOUND
