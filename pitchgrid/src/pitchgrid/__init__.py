"""Render a weekly timetable of pitch bookings as plain text."""

import datetime

__version__ = "1.0.0"

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def render_week(owner: str, week_start: datetime.date, bookings: list[dict]) -> str:
    lines = [f"Week of {week_start.isoformat()} for {owner}"]
    ordered = sorted(bookings, key=lambda b: (b["date"], b["start_hour"]))
    if not ordered:
        lines.append("No bookings")
    for booking in ordered:
        day = datetime.date.fromisoformat(booking["date"])
        lines.append(
            f"{DAY_NAMES[day.weekday()]:<10} {booking['start_hour']:02d}:00  Pitch {booking['pitch_id']}"
        )
    return "\n".join(lines)