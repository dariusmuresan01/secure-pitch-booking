import sqlite3
import os

from argon2 import PasswordHasher

hasher = PasswordHasher()
connection = sqlite3.connect(os.environ.get("DATABASE_PATH", "users.db"))


connection.execute("DROP TABLE IF EXISTS users")
connection.execute(
    """
    CREATE TABLE users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('player', 'admin'))
    )
    """
)


# Synthetic test accounts only
users = [
    ("darius", hasher.hash("darius-test-password"), "player"),
    ("rui", hasher.hash("rui-test-password"), "player"),
    ("admin", hasher.hash("admin-test-password"), "admin")
]


connection.executemany(
    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
    users,
)


connection.commit()
connection.close()
print("Seeded 3 accounts")