import datetime
import random

import pytest


def random_monday() -> datetime.date:
    """A random Monday far in the future, so every test gets an empty week."""
    first_monday = datetime.date(2100, 1, 4)
    return first_monday + datetime.timedelta(weeks=random.randint(0, 400000))


def book(client, headers, day: datetime.date, hour: int) -> dict:
    response = client.post(
        "/bookings",
        headers=headers,
        json={"pitch_id": 2, "date": day.isoformat(), "start_hour": hour},
    )
    assert response.status_code == 201, response.text
    return response.json()


def request_schedule(client, headers, monday: datetime.date):
    return client.post("/schedules", headers=headers, json={"week_start": monday.isoformat()})


def test_schedule_contains_only_own_active_bookings_of_that_week(client, darius, rui):
    monday = random_monday()
    book(client, darius, monday, 10)                                   # included
    book(client, rui, monday + datetime.timedelta(days=1), 11)         # other player
    cancelled = book(client, darius, monday + datetime.timedelta(days=2), 12)
    client.post(f"/bookings/{cancelled['id']}/cancel", headers=darius)  # cancelled
    book(client, darius, monday + datetime.timedelta(days=10), 13)     # next week

    created = request_schedule(client, darius, monday)
    assert created.status_code == 201
    schedule_id = created.json()["schedule_id"]

    downloaded = client.get(f"/schedules/{schedule_id}", headers=darius)
    assert downloaded.status_code == 200
    schedule = downloaded.json()
    content = schedule["content"]

    assert schedule["owner_id"] == "darius"
    assert schedule["week"] == monday.isoformat()
    assert content.startswith(f"Week of {monday.isoformat()} for darius")
    assert "Monday" in content and "10:00" in content
    assert "Tuesday" not in content      # rui's booking stays out (T11)
    assert "Wednesday" not in content    # cancelled booking stays out
    assert "Thursday" not in content     # booking from the next week stays out


def test_empty_week_gives_empty_schedule(client, rui):
    created = request_schedule(client, rui, random_monday())
    assert created.status_code == 201
    schedule = client.get(f"/schedules/{created.json()['schedule_id']}", headers=rui).json()
    assert "No bookings" in schedule["content"]


def test_other_player_cannot_download_schedule(client, darius, rui):
    schedule_id = request_schedule(client, darius, random_monday()).json()["schedule_id"]
    response = client.get(f"/schedules/{schedule_id}", headers=rui)
    assert response.status_code == 403


def test_admin_cannot_download_player_schedule(client, darius, admin):
    schedule_id = request_schedule(client, darius, random_monday()).json()["schedule_id"]
    response = client.get(f"/schedules/{schedule_id}", headers=admin)
    assert response.status_code == 403


def test_unknown_schedule_returns_404(client, darius):
    response = client.get("/schedules/999999", headers=darius)
    assert response.status_code == 404


def test_admin_cannot_request_schedule(client, admin):
    response = request_schedule(client, admin, random_monday())
    assert response.status_code == 403


@pytest.mark.parametrize("week_start", ["2030-01-08", "2030-13-01", "not-a-date"])
def test_invalid_week_start_is_rejected(client, darius, week_start):
    response = client.post("/schedules", headers=darius, json={"week_start": week_start})
    assert response.status_code == 422