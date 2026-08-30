"""SQLite data layer for Spendly.

Provides a connection factory plus schema creation and development seeding.
Standard library only (no ORM); all writes use parameterized queries.
"""

import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

# Project root is the parent of the database/ package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "spendly.db"

# Fixed category list — keep in sync with the rest of the app.
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    """Return a SQLite connection with row access by name and FK enforcement on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist. Safe to call repeatedly."""
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT NOT NULL,
                    email         TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL REFERENCES users(id),
                    amount      REAL NOT NULL,
                    category    TEXT NOT NULL,
                    date        TEXT NOT NULL,
                    description TEXT,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
    finally:
        conn.close()


def seed_db():
    """Insert one demo user and 8 sample expenses. No-op if users already exist."""
    conn = get_db()
    try:
        already_seeded = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if already_seeded:
            return

        with conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
            )
            user_id = cur.lastrowid

            # (day_of_month, amount ₹, category, description)
            sample_expenses = [
                (3, 480.0, "Food", "Groceries from the local kirana store"),
                (5, 60.0, "Transport", "Auto rickshaw to office"),
                (7, 1250.0, "Bills", "Electricity bill for the month"),
                (10, 350.0, "Health", "Pharmacy — monthly medicines"),
                (14, 299.0, "Entertainment", "OTT subscription renewal"),
                (18, 1899.0, "Shopping", "New pair of running shoes"),
                (22, 150.0, "Other", "Temple donation"),
                (25, 220.0, "Food", "Dinner at a Udupi restaurant"),
            ]

            today = date.today()
            month_prefix = f"{today.year:04d}-{today.month:02d}"
            conn.executemany(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (user_id, amount, category, f"{month_prefix}-{day:02d}", description)
                    for day, amount, category, description in sample_expenses
                ],
            )
    finally:
        conn.close()
