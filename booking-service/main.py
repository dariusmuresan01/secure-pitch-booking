import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATABASE = "booking.db"

app = FastAPI()


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
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
