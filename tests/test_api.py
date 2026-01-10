from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_list_files():
    response = client.get("/api/files")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
