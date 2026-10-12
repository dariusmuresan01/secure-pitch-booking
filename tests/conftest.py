import os

import httpx
import pytest

API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Synthetic test accounts, same as api/seed.py
PASSWORDS = {
    "darius": "darius-test-password",
    "rui": "rui-test-password",
    "admin": "admin-test-password",
}


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=API_URL, timeout=10.0) as http_client:
        yield http_client


def auth_headers(client: httpx.Client, username: str) -> dict:
    response = client.post(
        "/login",
        json={"username": username, "password": PASSWORDS[username]},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def darius(client):
    return auth_headers(client, "darius")


@pytest.fixture
def rui(client):
    return auth_headers(client, "rui")


@pytest.fixture
def admin(client):
    return auth_headers(client, "admin")