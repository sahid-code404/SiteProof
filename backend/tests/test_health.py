import os

os.environ["DATABASE_URL"] = "sqlite:///./test-siteproof.db"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
