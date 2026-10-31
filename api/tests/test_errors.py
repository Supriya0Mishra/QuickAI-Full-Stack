import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AppError, register_error_handlers


class Body(BaseModel):
    prompt: str = Field(min_length=1)


@pytest.fixture
def client() -> TestClient:
    """A small app with routes that trigger each kind of error."""
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/validate")
    async def validate(body: Body):
        return {"success": True}

    @app.get("/forbidden")
    async def forbidden():
        raise AppError(403, "Premium only.")

    @app.get("/crash")
    async def crash():
        raise RuntimeError("database password is hunter2")

    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_returns_400_with_field_name(client):
    response = client.post("/validate", json={"prompt": ""})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"].startswith("prompt:")


def test_app_error_keeps_status_and_message(client):
    response = client.get("/forbidden")

    assert response.status_code == 403
    assert response.json() == {"success": False, "message": "Premium only."}


def test_unexpected_error_hides_details(client):
    response = client.get("/crash")

    assert response.status_code == 500
    assert "hunter2" not in response.text
    assert response.json()["success"] is False
