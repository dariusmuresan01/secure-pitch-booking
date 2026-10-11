import sqlite3
import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATABASE = "booking.db"

app = FastAPI()


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@app.get("/health")
def health():
    return {"status": "ok", "service": "booking-service"}


@app.get("/pitches")
def list_pitches():
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, name, address, price_per_hour FROM pitches"
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


@app.get("/pitches/{pitch_id}")
def get_pitch(pitch_id: int):
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


# TODO: admin only (plan section 4)
@app.post("/pitches", status_code=201)
def create_pitch(pitch:PitchCreate): 
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
    user_id: str = Field(min_length=1, max_length=200)
    date: datetime.date
    start_hour: int = Field(gt=9, le=22)


# TODO: take user_id from the token, not from the body (threat T5)
@app.post("/bookings", status_code=201)
def create_booking(booking:BookingCreate):
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
            (booking.pitch_id, booking.user_id, booking.date.isoformat(), booking.start_hour)
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
        "user_id": booking.user_id,
        "date": booking.date.isoformat(),
        "start_hour": booking.start_hour,
        "status": "active"
    }


# TODO: take user_id from the token, not from the query (threat T10)
@app.get("/bookings")
def get_bookings(user_id: str):
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, pitch_id, user_id, date, start_hour, status FROM bookings WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# TODO: take user_id from the token, not from the query (threat T4); admin may cancel any booking
@app.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user_id: str):
    connection = get_connection()
    booking = connection.execute(
        "SELECT id, pitch_id, user_id, date, start_hour, status FROM bookings WHERE id = ?",
        (booking_id,),
    ).fetchone()
    if booking is None: 
        connection.close()
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["user_id"] != user_id:
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

