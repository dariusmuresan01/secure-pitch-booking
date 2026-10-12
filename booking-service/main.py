import sqlite3
import datetime
import jwt

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pathlib import Path

DATABASE = "booking.db"
PUBLIC_KEY = Path("../keys/public.pem").read_text()
bearer = HTTPBearer(auto_error=False)

app = FastAPI()


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@app.get("/health")
def health():
    return {"status": "ok", "service": "booking-service"}

def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try: 
        claims = jwt.decode(
            credentials.credentials,
            PUBLIC_KEY,
            algorithms=["EdDSA"],
            audience="booking-service",
            issuer="api",
            options={"require": ["iss", "sub", "aud", "iat", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return claims


@app.get("/pitches")
def list_pitches(user: dict = Depends(get_current_user)):
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, name, address, price_per_hour FROM pitches"
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


@app.get("/pitches/{pitch_id}")
def get_pitch(pitch_id: int, user: dict = Depends(get_current_user)):
    connection = get_connection()
    row = connection.execute(
        "SELECT id, name, address, price_per_hour FROM pitches WHERE id = ?",
        (pitch_id,),
    ).fetchone()
    connection.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Pitch not found")
    return dict(row)


class PitchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=200)
    price_per_hour: int = Field(gt=0, le=10000)


@app.post("/pitches", status_code=201)
def create_pitch(pitch:PitchCreate, user: dict = Depends(get_current_user)): 
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can add pitches")
    connection = get_connection()
    cursor = connection.execute(
        "INSERT INTO pitches (name, address, price_per_hour) VALUES (?, ?, ?)",
        (pitch.name, pitch.address, pitch.price_per_hour)
    )
    connection.commit()
    new_id = cursor.lastrowid
    connection.close()
    return {
        "id": new_id,
        "name": pitch.name,
        "address": pitch.address,
        "price_per_hour": pitch.price_per_hour
    }


class BookingCreate(BaseModel):
    pitch_id: int = Field(gt=0)
    date: datetime.date
    start_hour: int = Field(gt=9, le=22)


@app.post("/bookings", status_code=201)
def create_booking(booking:BookingCreate, user: dict = Depends(get_current_user)):
    if user["role"] != "player":
        raise HTTPException(status_code=403, detail="Only players can create bookings")
    connection = get_connection()
    pitch = connection.execute(
        "SELECT id FROM pitches WHERE id = ?",
        (booking.pitch_id,),
    ).fetchone()
    if pitch is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Pitch not found")
    try: 
        cursor = connection.execute(
            "INSERT INTO bookings (pitch_id, user_id, date, start_hour) VALUES (?, ?, ?, ?)",
            (booking.pitch_id, user["sub"], booking.date.isoformat(), booking.start_hour)
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        raise HTTPException(status_code=409, detail="The pitch is already booked in that hour")
    new_id = cursor.lastrowid
    connection.close()
    return {
        "id": new_id,
        "pitch_id": booking.pitch_id,
        "user_id": user["sub"],
        "date": booking.date.isoformat(),
        "start_hour": booking.start_hour,
        "status": "active"
    }


@app.get("/bookings")
def get_bookings(user: dict = Depends(get_current_user)):
    connection = get_connection()
    if user["role"] == "admin":
        rows = connection.execute(
            "SELECT id, pitch_id, user_id, date, start_hour, status FROM bookings"
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT id, pitch_id, user_id, date, start_hour, status FROM bookings WHERE user_id = ?",
            (user["sub"],),
        ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user: dict = Depends(get_current_user)):
    connection = get_connection()
    booking = connection.execute(
        "SELECT id, pitch_id, user_id, date, start_hour, status FROM bookings WHERE id = ?",
        (booking_id,),
    ).fetchone()
    if booking is None: 
        connection.close()
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["user_id"] != user["sub"] and user["role"] != "admin":
        connection.close()
        raise HTTPException(status_code=403, detail="Not allowed to cancel this booking")
    if booking["status"] != "active":
        connection.close()
        raise HTTPException(status_code=409, detail="Booking is already cancelled")
    connection.execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
        (booking_id,),
    )
    connection.commit()
    connection.close()
    result = dict(booking)
    result["status"] = "cancelled"
    return result


@app.delete("/pitches/{pitch_id}", status_code=204)
def delete_pitch(pitch_id: int, user: dict = Depends(get_current_user)):
    if user["role"] != "admin" :
        raise HTTPException(status_code=403, detail="Only admins can remove pitches")
    connection = get_connection()
    pitch = connection.execute(
        "SELECT id FROM pitches WHERE id = ?",
        (pitch_id,),
    ).fetchone()
    if pitch is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Pitch not found")
    try: 
        connection.execute(
            "DELETE FROM pitches WHERE id = ?",
            (pitch_id,),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        connection.close()
        raise HTTPException(status_code=409, detail="Pitch has bookings and cannot be removed")
    connection.close()