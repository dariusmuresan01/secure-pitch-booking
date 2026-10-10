from fastapi import FastAPI, HTTPException


app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "service": "booking-service"}


pitches = [
    {"id": 1, "name": "PRO Arena", "address": "Calea Feldioarei 98", "price_per_hour": 300},
    {"id": 2, "name": "Elite Arena", "address": "Calea București 17", "price_per_hour": 240},
]


@app.get("/pitches")
def list_pitches():
    return pitches


@app.get("/pitches/{pitch_id}")
def get_pitch(pitch_id: int):
    for pitch in pitches: 
        if pitch["id"] == pitch_id: 
            return pitch
    raise HTTPException(status_code=404, detail="Pitch not found")