"""V3 - CWE-20 Improper Input Validation of the booking date.

The date has a valid format, but secure mode also checks that it is not in the
past. Vulnerable mode skips that check, so a player can fabricate past bookings.
"""

import datetime
import os
import random

VULNERABLE_MODE = os.environ.get("VULNERABLE_MODE") == "1"


def test_v3_booking_in_the_past(client, darius):
    # A date range no other test file uses: 2000 to about 2019.
    past_day = datetime.date(2000, 1, 1) + datetime.timedelta(days=random.randint(0, 7000))
    body = {"pitch_id": 2, "date": past_day.isoformat(), "start_hour": random.randint(10, 22)}

    response = client.post("/bookings", headers=darius, json=body)

    if VULNERABLE_MODE:
        assert response.status_code == 201
        dates = {b["date"] for b in client.get("/bookings", headers=darius).json()}
        assert past_day.isoformat() in dates   # the fake booking is now stored
    else:
        assert response.status_code == 422