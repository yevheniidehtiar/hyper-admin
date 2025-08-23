import pytest
from examples.simple_app import User, app
from fastapi.testclient import TestClient

from hyperadmin.db import get_session

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_users():
    session = next(get_session())
    session.add(User(name="Alice", email="alice@example.com"))
    session.add(User(name="Bob", email="bob@example.com"))
    session.add(User(name="Charlie", email="charlie@example.com"))
    session.commit()
    return session


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Go to /admin/user to see the admin interface."}


def test_get_list_view():
    response = client.get("/admin/user")
    assert response.status_code == 200
    assert "User List" in response.text
    assert "Alice" in response.text


def test_get_detail_view():
    response = client.get("/admin/user/1")
    assert response.status_code == 200
    assert "User #1" in response.text
    assert "alice@example.com" in response.text


def test_get_detail_view_not_found():
    response = client.get("/admin/user/999")
    assert response.status_code == 404
