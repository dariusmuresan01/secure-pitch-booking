import base64
import json


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "api"


def test_login_with_valid_password_returns_token(client):
    response = client.post(
        "/login",
        json={"username": "darius", "password": "darius-test-password"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert "access_token" in response.json()


def test_login_errors_do_not_reveal_which_part_was_wrong(client):
    wrong_password = client.post(
        "/login",
        json={"username": "darius", "password": "wrong"},
    )
    unknown_user = client.post(
        "/login",
        json={"username": "nobody", "password": "wrong"},
    )
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_request_without_token_is_rejected(client):
    response = client.get("/pitches")
    assert response.status_code == 401


def test_tampered_token_is_rejected(client, darius):
    token = darius["Authorization"].removeprefix("Bearer ")
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["role"] = "admin"
    forged_payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    )
    forged_token = f"{header}.{forged_payload}.{signature}"
    response = client.get(
        "/bookings",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401