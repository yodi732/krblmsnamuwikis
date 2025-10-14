#!/usr/bin/env python3

"""
SQLite DB autofix for Render free plan.

- Creates "user" and "document" tables if missing
- Adds missing columns:
    - user.password
    - document.created_by
- Safe no-op when already up-to-date
- Compatible with existing data
"""
import os
import re
import sqlite3
from urllib.parse import urlparse

def _sqlite_path_from_database_url(url: str) -> str:
    # Accept forms like sqlite:///app.db, sqlite:////data/app.db, or plain 'app.db'
    if not url or url.strip() == "":
        return "app.db"
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    if url.startswith("sqlite:////"):
        return url.replace("sqlite:////", "/", 1)
    # If someone passed a filename, just use it
    if url.endswith(".db") and "://" not in url:
        return url
    # Fallback to local app.db
    return "app.db"

def ensure_tables_and_columns(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Create tables if not exist (minimal, non-destructive)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS "user" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS "document" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            parent_id INTEGER,
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(parent_id) REFERENCES document(id) ON DELETE SET NULL
        )
    """)

    # 2) Add missing columns (idempotent)
    def table_has_column(table, col):
        cur.execute(f'PRAGMA table_info("{table}")')
        return any(r["name"] == col for r in cur.fetchall())

    # user.password
    if not table_has_column("user", "password"):
        cur.execute('ALTER TABLE "user" ADD COLUMN password TEXT')

    # document.created_by
    if not table_has_column("document", "created_by"):
        cur.execute('ALTER TABLE "document" ADD COLUMN created_by TEXT')

    # Optional: ensure updated_at exists
    if not table_has_column("document", "updated_at"):
        cur.execute('ALTER TABLE "document" ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
    db_path = _sqlite_path_from_database_url(database_url)
    ensure_tables_and_columns(db_path)
    print("[prestart] DB autofix completed for", db_path)
