import sqlite3
import datetime
import jwt
import httpx

from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

DATABASE = "users.db"
PRIVATE_KEY = Path("../keys/private.pem").read_text()
TOKEN_LIFETIME = datetime.timedelta(minutes=15)
PUBLIC_KEY = Path("../keys/public.pem").read_text()
BOOKING_SERVICE_URL = "http://localhost:8001"
bearer = HTTPBearer(auto_error=False)

app = FastAPI()
hasher = PasswordHasher()

@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


def create_token(username: str, role: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "iss": "api",
        "sub": username,
        "role": role,
        "aud": ["booking-service"],
        "iat": now,
        "exp": now + TOKEN_LIFETIME
    }
    return jwt.encode(claims, PRIVATE_KEY, algorithm="EdDSA")


def get_verified_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(
            credentials.credentials,
            PUBLIC_KEY,
            algorithms=["EdDSA"],
            audience="booking-service",
            issuer="api",
            options={"require": ["iss", "sub", "aud", "iat", "exp"]}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return credentials.credentials


def forward(method: str, path: str, token: str, body: dict | None = None) -> Response:
    try:
        response = httpx.request(
            method,
            BOOKING_SERVICE_URL + path,
            headers={"Authorization": f"Bearer {token}"},
            json=body,
            timeout=5.0
        )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Booking service unavailable")
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type")
    )


@app.post("/login")
def login(credentials: LoginRequest):
    connection = get_connection()
    user = connection.execute(
        "SELECT username, password_hash, role FROM users WHERE username = ?",
        (credentials.username,)
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