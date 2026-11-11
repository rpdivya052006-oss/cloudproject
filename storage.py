
import os
import sqlite3
from pathlib import Path

DB_PATH = Path("foodbridge.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            donation_id TEXT PRIMARY KEY,
            donor_name TEXT,
            food_name TEXT,
            category TEXT,
            quantity INTEGER,
            location TEXT,
            expiry_time TEXT,
            notes TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'Available',
            claimed_by TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    return conn


class LocalStorage:

    mode = "Local SQLite demo mode"

    def list_donations(self):
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM donations ORDER BY created_at DESC"
            ).fetchall()

            return [dict(row) for row in rows]

    def add_donation(self, item):
        with _connect() as conn:
            conn.execute("""
                INSERT INTO donations (
                    donation_id, donor_name, food_name,
                    category, quantity, location, expiry_time,
                    notes, image_url, status, claimed_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["donation_id"],
                item["donor_name"],
                item["food_name"],
                item["category"],
                item["quantity"],
                item["location"],
                item["expiry_time"],
                item.get("notes", ""),
                item.get("image_url", ""),
                "Available",
                "",
                item["created_at"]
            ))

            conn.commit()

    def update_status(self, donation_id, status, claimed_by=""):
        with _connect() as conn:
            result = conn.execute("""
                UPDATE donations
                SET status=?, claimed_by=?
                WHERE donation_id=? AND status='Available'
            """, (status, claimed_by, donation_id))

            conn.commit()
            return result.rowcount > 0

    def upload_image(self, uploaded_file):
        return ""


def get_storage():
    return LocalStorage()


