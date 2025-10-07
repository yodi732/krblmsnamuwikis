
from pathlib import Path
import sqlite3, os

HERE = Path(__file__).parent
INSTANCE = HERE / "instance"
INSTANCE.mkdir(exist_ok=True)
DB_PATH = INSTANCE / "database.db"
SCHEMA = HERE / "schema.sql"

def init_db():
    if SCHEMA.exists():
        with sqlite3.connect(str(DB_PATH)) as conn:
            with open(SCHEMA, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()
        print("Initialized DB at", DB_PATH)
    else:
        print("No schema.sql found; skipping.")

if __name__ == "__main__":
    init_db()
