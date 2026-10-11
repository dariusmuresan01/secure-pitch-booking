import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

DATABASE = "users.db"

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
    return {"username": user["username"], "role": user["role"]}