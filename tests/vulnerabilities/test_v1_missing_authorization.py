"""V1 - CWE-862 Missing Authorization on GET /schedules/{id} (threat T10).

The test runs in both modes and checks what each mode should do:
secure mode blocks the cross-player download, vulnerable mode lets it through.
"""

import datetime
import os
import random

VULNERABLE_MODE = os.environ.get("VULNERABLE_MODE") == "1"


def random_monday() -> datetime.date:
    first_monday = datetime.date(2100, 1, 4)
    return first_monday + datetime.timedelta(weeks=random.randint(0, 400000))


def test_v1_other_player_reads_schedule(client, darius, andreea):
    # Darius creates a schedule that belongs to him.
    created = client.post(
        "/schedules", headers=darius, json={"week_start": random_monday().isoformat()}
    )
    assert created.status_code == 201
    schedule_id = created.json()["schedule_id"]

    # Andreea is logged in, but asks for Darius's schedule id.
    response = client.get(f"/schedules/{schedule_id}", headers=andreea)

    if VULNERABLE_MODE:
        assert response.status_code == 200
        assert response.json()["owner_id"] == "darius"
    else:
        assert response.status_code == 403