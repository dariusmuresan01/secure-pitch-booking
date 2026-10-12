import datetime
import random

import pytest


def free_slot() -> dict:
    """A random future slot on pitch 2, so tests never collide with each other
    or with data left over from earlier runs."""
    day = datetime.date(2030, 1, 1) + datetime.timedelta(days=random.randint(0, 25000))
    return {"pitch_id": 2, "date": day.isoformat(), "start_hour": random.randint(10, 22)}


def create_booking(client, headers) -> dict:
    for _ in range(5):
        response = client.post("/bookings", headers=headers, json=free_slot())
        if response.status_code == 201:
            return response.json()
    pytest.fail(f"could not create a booking: {response.status_code} {response.text}")


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/pitches"),
        ("GET", "/pitches/1"),
        ("POST", "/pitches"),
        ("DELETE", "/pitches/1"),
        ("POST", "/bookings"),
        ("GET", "/bookings"),
        ("POST", "/bookings/1/cancel"),
        ("POST", "/schedules"),
        ("GET", "/schedules/1"),
    ],
)
def test_anonymous_requests_are_rejected(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401


def test_player_can_view_pitches(client, darius):
    response = client.get("/pitches", headers=darius)
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_player_cannot_add_pitch(client, darius):
    response = client.post(
        "/pitches",
        headers=darius,
        json={"name": "Fake", "address": "Nowhere 1", "price_per_hour": 1},
    )
    assert response.status_code == 403


def test_player_cannot_remove_pitch(client, darius, admin):
    created = client.post(
        "/pitches",
        headers=admin,
        json={"name": "Temporary", "address": "Test 1", "price_per_hour": 100},
    )
    assert created.status_code == 201
    pitch_id = created.json()["id"]

    response = client.delete(f"/pitches/{pitch_id}", headers=darius)
    assert response.status_code == 403
    assert client.get(f"/pitches/{pitch_id}", headers=admin).status_code == 200

    assert client.delete(f"/pitches/{pitch_id}", headers=admin).status_code == 204


def test_pitch_with_bookings_cannot_be_removed(client, darius, admin):
    create_booking(client, darius)
    response = client.delete("/pitches/2", headers=admin)
    assert response.status_code == 409


def test_player_can_book_free_slot(client, darius):
    booking = create_booking(client, darius)
    assert booking["user_id"] == "darius"
    assert booking["status"] == "active"


def test_booking_owner_is_taken_from_token_not_body(client, darius):
    body = free_slot() | {"user_id": "rui"}
    response = client.post("/bookings", headers=darius, json=body)
    assert response.status_code == 201
    assert response.json()["user_id"] == "darius"


def test_same_slot_cannot_be_booked_twice(client, darius, rui):
    slot = free_slot()
    assert client.post("/bookings", headers=darius, json=slot).status_code == 201
    assert client.post("/bookings", headers=rui, json=slot).status_code == 409


def test_admin_cannot_create_booking(client, admin):
    response = client.post("/bookings", headers=admin, json=free_slot())
    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"pitch_id": 2, "date": "2030-01-01", "start_hour": 9},
        {"pitch_id": 2, "date": "2030-01-01", "start_hour": 23},
        {"pitch_id": 2, "date": "2030-13-45", "start_hour": 18},
        {"pitch_id": 0, "date": "2030-01-01", "start_hour": 18},
        {"pitch_id": "1 OR 1=1", "date": "2030-01-01", "start_hour": 18},
    ],
)
def test_malformed_booking_is_rejected(client, darius, body):
    response = client.post("/bookings", headers=darius, json=body)
    assert response.status_code == 422


def test_player_sees_only_own_bookings(client, darius, rui):
    create_booking(client, rui)
    bookings = client.get("/bookings", headers=darius).json()
    assert bookings
    assert {booking["user_id"] for booking in bookings} == {"darius"}


def test_admin_sees_all_bookings(client, admin, darius, rui):
    create_booking(client, darius)
    create_booking(client, rui)
    bookings = client.get("/bookings", headers=admin).json()
    assert {"darius", "rui"} <= {booking["user_id"] for booking in bookings}


def test_player_cannot_cancel_other_players_booking(client, darius, rui):
    booking = create_booking(client, darius)

    response = client.post(f"/bookings/{booking['id']}/cancel", headers=rui)
    assert response.status_code == 403

    darius_bookings = client.get("/bookings", headers=darius).json()
    still_there = next(b for b in darius_bookings if b["id"] == booking["id"])
    assert still_there["status"] == "active"


def test_player_can_cancel_own_booking_once(client, darius):
    booking = create_booking(client, darius)
    first = client.post(f"/bookings/{booking['id']}/cancel", headers=darius)
    second = client.post(f"/bookings/{booking['id']}/cancel", headers=darius)
    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert second.status_code == 409


def test_admin_can_cancel_any_booking(client, admin, rui):
    booking = create_booking(client, rui)
    response = client.post(f"/bookings/{booking['id']}/cancel", headers=admin)
    assert response.status_code == 200


def test_cancelling_unknown_booking_returns_404(client, darius):
    response = client.post("/bookings/999999/cancel", headers=darius)
    assert response.status_code == 404