import sqlite3

connection = sqlite3.connect("booking.db")

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

pitches = [
    ("Pro Arena", "Calea Feldioarei 98", 300),
    ("Elite Arena", "Calea București 17", 240)
]

connection.executemany(
    "INSERT INTO pitches (name, address, price_per_hour) VALUES (?, ?, ?)",
    pitches
)

connection.commit()
connection.close()
print("Seeded 2 pitches")