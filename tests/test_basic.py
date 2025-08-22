from fastapi.testclient import TestClient
import sys
import os

# Add the root directory to the Python path to allow importing from 'examples'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from examples.simple_app import app

client = TestClient(app)

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
