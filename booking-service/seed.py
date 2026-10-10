import sqlite3

connection = sqlite3.connect("booking.db")

connection.execute("DROP TABLE IF EXISTS bookings")

connection.execute("DROP TABLE IF EXISTS pitches")

connection.execute(
    """
    CREATE TABLE pitches (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        price_per_hour INTEGER NOT NULL
    )
    """
)

connection.execute(
    """
    CREATE TABLE bookings (
        id INTEGER PRIMARY KEY,
        pitch_id INTEGER NOT NULL REFERENCES pitches (id),
        user_id TEXT NOT NULL,
        date TEXT NOT NULL,
        start_hour INTEGER NOT NULL CHECK (start_hour BETWEEN 10 AND 22),
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'cancelled'))
    )
    """
)

connection.execute(
    """
    CREATE UNIQUE INDEX one_active_booking_per_hour 
    ON bookings (pitch_id, date, start_hour)
    WHERE status = 'active'
    """
)

pitches = [
    ("Pro Arena", "Calea Feldioarei 98", 300),
    ("Elite Arena", "Calea București 17", 240)
]

bookings = [
    (1, "darius", "2026-10-20", 20),
    (1, "rui", "2026-10-24", 18)
]

connection.executemany(
    "INSERT INTO pitches (name, address, price_per_hour) VALUES (?, ?, ?)",
    pitches
)

connection.executemany(
    "INSERT INTO bookings (pitch_id, user_id, date, start_hour) VALUES (?,?,?,?)",
    bookings
)

connection.commit()
connection.close()
print("Seeded 2 pitches with bookings")