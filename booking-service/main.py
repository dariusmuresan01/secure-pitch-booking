from fastapi import FastAPI


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