"""Tests that talk to the internal services directly.

They only run inside the Docker test container, which sits on the internal
network (INTERNAL_TESTS=1). From the laptop these services are unreachable on
purpose, so the tests are skipped there.

The test container holds the signing key so it can play the role of the api
and mint job tokens with deliberately wrong or narrowed claims.
"""

import datetime
import os
import random
from pathlib import Path

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

pytestmark = pytest.mark.skipif(
    os.environ.get("INTERNAL_TESTS") != "1",
    reason="internal services are only reachable from the Docker test container",
)

BOOKING_URL = os.environ.get("BOOKING_SERVICE_URL", "http://booking-service:8001")
SCHEDULE_URL = os.environ.get("SCHEDULE_SERVICE_URL", "http://schedule-service:8002")
PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH", "/run/keys/private.pem")


def signing_key() -> str:
    return Path(PRIVATE_KEY_PATH).read_text()


def other_key() -> bytes:
    """A valid Ed25519 key that the services have never seen."""
    return Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def job_token(key=None, **overrides) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "iss": "api",
        "sub": "darius",
        "token_use": "job",
        "aud": ["schedule-service", "booking-service"],
        "week": "2030-01-07",
        "scope": ["bookings:read", "schedules:write"],
        "iat": now,
        "exp": now + datetime.timedelta(minutes=2),
    }
    claims.update(overrides)
    return jwt.encode(claims, key or signing_key(), algorithm="EdDSA")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def random_monday() -> datetime.date:
    return datetime.date(2030, 1, 7) + datetime.timedelta(weeks=random.randint(0, 3000))


def book(client, headers, day: datetime.date, hour: int) -> int:
    response = client.post(
        "/bookings",
        headers=headers,
        json={"pitch_id": 2, "date": day.isoformat(), "start_hour": hour},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_job_token_reads_only_its_player_and_week(client, darius, rui):
    monday = random_monday()
    own = book(client, darius, monday, 10)
    book(client, rui, monday, 11)
    book(client, darius, monday + datetime.timedelta(days=8), 12)

    token = job_token(week=monday.isoformat())
    response = httpx.get(f"{BOOKING_URL}/jobs/bookings", headers=bearer(token))

    assert response.status_code == 200
    assert [booking["id"] for booking in response.json()] == [own]


def test_job_token_without_read_scope_is_forbidden():
    token = job_token(scope=["schedules:write"])
    response = httpx.get(f"{BOOKING_URL}/jobs/bookings", headers=bearer(token))
    assert response.status_code == 403


def test_job_token_without_write_scope_cannot_save_schedule():
    token = job_token(scope=["bookings:read"])
    response = httpx.post(
        f"{BOOKING_URL}/jobs/schedules", headers=bearer(token), json={"content": "x"}
    )
    assert response.status_code == 403


def test_saved_schedule_owner_comes_from_job_token():
    token = job_token()
    response = httpx.post(
        f"{BOOKING_URL}/jobs/schedules",
        headers=bearer(token),
        json={"content": "test", "owner_id": "rui", "week": "2099-01-05"},
    )
    assert response.status_code == 201
    assert response.json()["owner_id"] == "darius"
    assert response.json()["week"] == "2030-01-07"


def test_oversized_schedule_is_rejected():
    token = job_token()
    response = httpx.post(
        f"{BOOKING_URL}/jobs/schedules", headers=bearer(token), json={"content": "x" * 10001}
    )
    assert response.status_code == 422


def test_booking_service_rejects_job_token_signed_with_unknown_key():
    token = job_token(key=other_key())
    response = httpx.get(f"{BOOKING_URL}/jobs/bookings", headers=bearer(token))
    assert response.status_code == 401


def test_schedule_service_rejects_job_token_signed_with_unknown_key():
    token = job_token(key=other_key())
    response = httpx.post(f"{SCHEDULE_URL}/jobs", headers=bearer(token))
    assert response.status_code == 401


def test_expired_job_token_is_rejected():
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    token = job_token(iat=past, exp=past + datetime.timedelta(minutes=2))
    response = httpx.get(f"{BOOKING_URL}/jobs/bookings", headers=bearer(token))
    assert response.status_code == 401


def test_job_token_not_meant_for_schedule_service_is_rejected():
    token = job_token(aud=["booking-service"])
    response = httpx.post(f"{SCHEDULE_URL}/jobs", headers=bearer(token))
    assert response.status_code == 401


def test_job_token_cannot_be_used_as_user_token():
    response = httpx.get(f"{BOOKING_URL}/bookings", headers=bearer(job_token()))
    assert response.status_code == 401


def test_user_token_cannot_be_used_as_job_token(darius):
    response = httpx.get(f"{BOOKING_URL}/jobs/bookings", headers=darius)
    assert response.status_code == 401


def test_user_token_is_rejected_by_schedule_service(darius):
    response = httpx.post(f"{SCHEDULE_URL}/jobs", headers=darius)
    assert response.status_code == 401


def test_booking_service_rejects_requests_without_token():
    response = httpx.get(f"{BOOKING_URL}/bookings")
    assert response.status_code == 401