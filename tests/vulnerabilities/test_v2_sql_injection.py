"""V2 - CWE-89 SQL Injection in the status filter of GET /bookings (threat T6).

Each test runs in both modes and checks what that mode should do:
secure mode rejects the crafted value, vulnerable mode leaks other players' bookings.
"""

import datetime
import os
import random

import pytest

VULNERABLE_MODE = os.environ.get("VULNERABLE_MODE") == "1"


def book_for(client, headers) -> dict:
    """Create a booking in a date range no other test file uses."""
    for _ in range(5):
        day = datetime.date(2099, 1, 1) + datetime.timedelta(days=random.randint(0, 360))
        response = client.post(
            "/bookings",
            headers=headers,
            json={"pitch_id": 2, "date": day.isoformat(), "start_hour": random.randint(10, 22)},
        )
        if response.status_code == 201:
            return response.json()
    pytest.fail(f"could not create a booking: {response.status_code} {response.text}")


def test_v2_normal_status_filter_works(client, darius):
    book_for(client, darius)
    response = client.get("/bookings", headers=darius, params={"status": "active"})
    assert response.status_code == 200
    bookings = response.json()
    assert bookings
    assert {b["user_id"] for b in bookings} == {"darius"}
    assert {b["status"] for b in bookings} == {"active"}


def test_v2_crafted_status_reads_other_players_bookings(client, darius, rui):
    book_for(client, darius)  # make sure another player has data to leak

    # Rui is logged in, but sends SQL text instead of a status value.
    response = client.get("/bookings", headers=rui, params={"status": "x' OR '1'='1"})

    if VULNERABLE_MODE:
        assert response.status_code == 200
        assert "darius" in {b["user_id"] for b in response.json()}
    else:
        assert response.status_code == 422