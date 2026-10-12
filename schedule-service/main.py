import datetime
from pathlib import Path

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pitchgrid import render_week

PUBLIC_KEY = Path("../keys/public.pem").read_text()
BOOKING_SERVICE_URL = "http://localhost:8001"
bearer = HTTPBearer(auto_error=False)

app = FastAPI()


def get_job(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> tuple[str, dict]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        claims = jwt.decode(
            credentials.credentials,
            PUBLIC_KEY,
            algorithms=["EdDSA"],
            audience="schedule-service",
            issuer="api",
            options={
                "require": ["iss", "sub", "aud", "iat", "exp", "token_use", "week", "scope"]
            },
        )
        datetime.date.fromisoformat(claims["week"])
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if claims["token_use"] != "job":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return credentials.credentials, claims


@app.get("/health")
def health():
    return {"status": "ok", "service": "schedule-service"}


@app.post("/jobs", status_code=201)
def run_schedule_job(job: tuple[str, dict] = Depends(get_job)):
    token, claims = job
    headers = {"Authorization": f"Bearer {token}"}

    try:
        bookings_response = httpx.get(
            f"{BOOKING_SERVICE_URL}/jobs/bookings",
            headers=headers,
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Booking service unavailable")
    if bookings_response.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not read bookings for this job")

    week_start = datetime.date.fromisoformat(claims["week"])
    content = render_week(claims["sub"], week_start, bookings_response.json())

    try:
        save_response = httpx.post(
            f"{BOOKING_SERVICE_URL}/jobs/schedules",
            headers=headers,
            json={"content": content},
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Booking service unavailable")
    if save_response.status_code != 201:
        raise HTTPException(status_code=502, detail="Could not save schedule")

    return {"schedule_id": save_response.json()["id"]}