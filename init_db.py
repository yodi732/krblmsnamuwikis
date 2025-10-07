
from pathlib import Path
import sqlite3

HERE = Path(__file__).parent
INSTANCE_DIR = HERE / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = INSTANCE_DIR / "database.db"
SCHEMA_PATH = HERE / "schema.sql"

if SCHEMA_PATH.exists():
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    print(f"Initialized DB at {DB_PATH}")
else:
    print("schema.sql not found, skipping")
