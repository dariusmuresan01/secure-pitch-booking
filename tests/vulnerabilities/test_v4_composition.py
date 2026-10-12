"""V4 - Composition vulnerability in operation 5 (threat T11).

The Booking service treats /jobs/bookings as a weekly feed for trusted jobs,
and the Schedule service assumes that feed is already limited to one player.
Each assumption looks fine alone; together, nobody filters by player.
The test goes through all three components via the public api.
"""

import datetime
import os
import random

VULNERABLE_MODE = os.environ.get("VULNERABLE_MODE") == "1"


def random_monday() -> datetime.date:
    # Weeks after the range test_schedules.py uses, so the week starts empty.
    first_monday = datetime.date(2100, 1, 4)
    return first_monday + datetime.timedelta(weeks=random.randint(400001, 410000))


def book(client, headers, day: datetime.date, hour: int):
    response = client.post(
        "/bookings",
        headers=headers,
        json={"pitch_id": 2, "date": day.isoformat(), "start_hour": hour},
    )
    assert response.status_code == 201, response.text


def test_v4_schedule_leaks_other_players_bookings(client, darius, andreea):
    monday = random_monday()
    book(client, darius, monday, 10)                                # Darius: Monday 10:00
    book(client, andreea, monday + datetime.timedelta(days=1), 18)      # Andreea: Tuesday 18:00

    # Darius asks for his own schedule: api -> schedule-service -> booking-service.
    created = client.post("/schedules", headers=darius, json={"week_start": monday.isoformat()})
    assert created.status_code == 201
    schedule = client.get(f"/schedules/{created.json()['schedule_id']}", headers=darius).json()
    content = schedule["content"]

    assert "Monday" in content and "10:00" in content   # his own booking is always there
    if VULNERABLE_MODE:
        assert "Tuesday" in content and "18:00" in content   # Andreea's booking leaked
    else:
        assert "Tuesday" not in content