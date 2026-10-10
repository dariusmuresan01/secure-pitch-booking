import sqlite3

from fastapi import FastAPI, HTTPException

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
