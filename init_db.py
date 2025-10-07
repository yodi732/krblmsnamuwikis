import sqlite3, os
from pathlib import Path

HERE = Path(__file__).parent
INSTANCE = HERE / "instance"
INSTANCE.mkdir(exist_ok=True)
DB_PATH = INSTANCE / "database.db"
SCHEMA = HERE / "schema.sql"

with sqlite3.connect(DB_PATH) as conn:
    if SCHEMA.exists():
        with open(SCHEMA, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
print("Initialized DB at", DB_PATH)
