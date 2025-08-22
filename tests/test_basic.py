from fastapi.testclient import TestClient
import sys
import os

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.simple_app import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Go to /admin/user to see the admin interface."}

def test_get_list_view():
    response = client.get("/admin/user")
    assert response.status_code == 200
    # Check if the response contains some expected text from the template
    assert "User List" in response.text
    assert "Alice" in response.text
    assert "Bob" in response.text

def test_get_detail_view():
    response = client.get("/admin/user/1")
    assert response.status_code == 200
    assert "User #1" in response.text
    assert "alice@example.com" in response.text

def test_get_detail_view_not_found():
    response = client.get("/admin/user/999")
    assert response.status_code == 404
