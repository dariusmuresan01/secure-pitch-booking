import datetime
import sqlite3
import os
from pathlib import Path

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

DATABASE = os.environ.get("DATABASE_PATH", "users.db")
PRIVATE_KEY = Path(os.environ.get("PRIVATE_KEY_PATH", "../keys/private.pem")).read_text()
PUBLIC_KEY = Path(os.environ.get("PUBLIC_KEY_PATH", "../keys/public.pem")).read_text()
TOKEN_LIFETIME = datetime.timedelta(minutes=15)
JOB_TOKEN_LIFETIME = datetime.timedelta(minutes=2)
BOOKING_SERVICE_URL = os.environ.get("BOOKING_SERVICE_URL", "http://localhost:8001")
SCHEDULE_SERVICE_URL = os.environ.get("SCHEDULE_SERVICE_URL", "http://localhost:8002")
bearer = HTTPBearer(auto_error=False)

app = FastAPI()
hasher = PasswordHasher()


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class PitchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=200)
    price_per_hour: int = Field(gt=0, le=10000)


class BookingCreate(BaseModel):
    pitch_id: int = Field(gt=0)
    date: datetime.date
    start_hour: int = Field(ge=10, le=22)


class ScheduleRequest(BaseModel):
    week_start: datetime.date


# ---------- Tokens ----------


def create_token(username: str, role: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "iss": "api",
        "sub": username,
        "role": role,
        "token_use": "access",
        "aud": ["booking-service"],
        "iat": now,
        "exp": now + TOKEN_LIFETIME,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="EdDSA")


def create_job_token(username: str, week: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "iss": "api",
        "sub": username,
        "token_use": "job",
        "aud": ["schedule-service", "booking-service"],
        "week": week,
        "scope": ["bookings:read", "schedules:write"],
        "iat": now,
        "exp": now + JOB_TOKEN_LIFETIME,
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="EdDSA")


def verify_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["EdDSA"],
            audience="booking-service",
            issuer="api",
            options={"require": ["iss", "sub", "aud", "iat", "exp", "token_use"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if claims["token_use"] != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return claims


def get_verified_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    verify_access_token(credentials.credentials)
    return credentials.credentials


def get_verified_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_access_token(credentials.credentials)


def forward(method: str, path: str, token: str, body: dict | None = None) -> Response:
    try:
        response = httpx.request(
            method,
            BOOKING_SERVICE_URL + path,
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Booking service unavailable")
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}


@app.post("/login")
def login(credentials: LoginRequest):
    connection = get_connection()
    user = connection.execute(
        "SELECT username, password_hash, role FROM users WHERE username = ?",
        (credentials.username,),
    ).fetchone()
    connection.close()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    try:
        hasher.verify(user["password_hash"], credentials.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/pitches")
def list_pitches(token: str = Depends(get_verified_token)):
    return forward("GET", "/pitches", token)


@app.get("/pitches/{pitch_id}")
def get_pitch(pitch_id: int, token: str = Depends(get_verified_token)):
    return forward("GET", f"/pitches/{pitch_id}", token)


@app.post("/pitches")
def create_pitch(pitch: PitchCreate, token: str = Depends(get_verified_token)):
    return forward("POST", "/pitches", token, pitch.model_dump(mode="json"))


@app.delete("/pitches/{pitch_id}")
def delete_pitch(pitch_id: int, token: str = Depends(get_verified_token)):
    return forward("DELETE", f"/pitches/{pitch_id}", token)


@app.post("/bookings")
def create_booking(booking: BookingCreate, token: str = Depends(get_verified_token)):
    return forward("POST", "/bookings", token, booking.model_dump(mode="json"))


@app.get("/bookings")
def get_bookings(token: str = Depends(get_verified_token)):
    return forward("GET", "/bookings", token)


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, token: str = Depends(get_verified_token)):
    return forward("POST", f"/bookings/{booking_id}/cancel", token)


@app.post("/schedules", status_code=201)
def request_schedule(request: ScheduleRequest, user: dict = Depends(get_verified_claims)):
    if user["role"] != "player":
        raise HTTPException(status_code=403, detail="Only players can request schedules")
    if request.week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be a Monday")
    job_token = create_job_token(user["sub"], request.week_start.isoformat())
    try:
        response = httpx.post(
            f"{SCHEDULE_SERVICE_URL}/jobs",
            headers={"Authorization": f"Bearer {job_token}"},
            timeout=10.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Schedule service unavailable")
    if response.status_code != 201:
        raise HTTPException(status_code=502, detail="Could not create schedule")
    return {"schedule_id": response.json()["schedule_id"]}


@app.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: int, token: str = Depends(get_verified_token)):
    return forward("GET", f"/schedules/{schedule_id}", token)